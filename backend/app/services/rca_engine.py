import logging
import networkx as nx
from typing import List, Dict, Any, Set
from sqlalchemy.orm import Session
from app.models.models import Device, TopologyLink, Incident, Interface

logger = logging.getLogger("ENOTP_RCA")

class RCAEngine:
    def __init__(self, db_session: Session):
        self.db = db_session

    def run_root_cause_analysis(self) -> Dict[str, Any]:
        """Performs topological analysis on all offline/degraded devices to isolate the root cause."""
        logger.info("Executing topological Root Cause Analysis (RCA)...")

        # 1. Fetch devices and topology links
        devices = self.db.query(Device).all()
        links = self.db.query(TopologyLink).all()

        if not devices:
            return {"status": "no_devices", "root_causes": []}

        # 2. Build networkx graph representing the network topology
        G = nx.Graph()
        
        # Add nodes with status attributes
        device_map = {}
        for dev in devices:
            G.add_node(dev.id, hostname=dev.hostname, status=dev.status, type=dev.device_type)
            device_map[dev.id] = dev

        # Add edges
        for link in links:
            G.add_edge(link.source_device_id, link.target_device_id, type=link.link_type)

        # 3. Find Core Gateway node (usually the core switch or firewalls)
        # We find a device marked as core_switch or router closest to the center
        core_nodes = [dev.id for dev in devices if dev.device_type == "switch" and "core" in dev.hostname.lower()]
        if not core_nodes:
            # Fallback to any online router or first device
            core_nodes = [dev.id for dev in devices if dev.status == "online"]
        
        if not core_nodes:
            # Entire network is offline or no core detected
            return {"status": "all_offline_or_no_core", "root_causes": []}

        core_node = core_nodes[0]

        # 4. Identify all offline devices
        offline_device_ids = {dev.id for dev in devices if dev.status == "offline"}
        if not offline_device_ids:
            logger.info("RCA: All monitored devices are online. No incidents to correlate.")
            return {"status": "healthy", "root_causes": []}

        # 5. Group failures and isolate root causes using BFS/DFS path analysis
        # For each offline device, check if its path to the Core Node contains another offline device.
        # The first offline device encountered along the path from the core to the target is the root cause.
        root_causes: Dict[str, List[str]] = {} # RootCauseID -> List of DownstreamAffectedDeviceIDs
        independent_failures: Set[str] = set()

        for off_id in offline_device_ids:
            if off_id == core_node:
                independent_failures.add(off_id)
                continue

            try:
                # Find shortest path from Core to the offline device
                path = nx.shortest_path(G, source=core_node, target=off_id)
                
                # Analyze the path (Core -> Node 1 -> Node 2 -> ... -> Target)
                # Find the FIRST node in this path that is offline
                first_offline_in_path = None
                for node in path:
                    if node in offline_device_ids:
                        first_offline_in_path = node
                        break
                
                if first_offline_in_path:
                    if first_offline_in_path == off_id:
                        # No prior failures on the path, this is an independent edge failure
                        independent_failures.add(off_id)
                    else:
                        # This node is offline because the ancestor is offline
                        if first_offline_in_path not in root_causes:
                            root_causes[first_offline_in_path] = []
                        root_causes[first_offline_in_path].append(off_id)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                # No topological connection in graph, treat as independent failure
                independent_failures.add(off_id)

        # 6. Format and consolidate Incidents in the Database
        consolidated_alerts = []
        for rc_id in independent_failures.union(root_causes.keys()):
            rc_device = device_map[rc_id]
            affected_ids = root_causes.get(rc_id, [])
            affected_devices = [device_map[a_id] for a_id in affected_ids]

            affected_hostnames = [d.hostname for d in affected_devices]
            impacted_sites = list({d.site for d in affected_devices + [rc_device]})

            # Calculate business impact and severity
            severity = "critical"
            if len(affected_devices) > 10:
                severity = "critical"
            elif len(affected_devices) > 2:
                severity = "major"
            else:
                severity = "minor"

            title = f"RCA: Power/Connectivity Loss on {rc_device.hostname}"
            description = (
                f"Topological root-cause engine identified {rc_device.hostname} ({rc_device.ip_address}) as the single point of failure.\n\n"
                f"Root Cause Device: {rc_device.hostname} ({rc_device.device_type.upper()})\n"
                f"Directly Affected Downstream Devices ({len(affected_hostnames)}): {', '.join(affected_hostnames) if affected_hostnames else 'None'}\n"
                f"Impacted Sites: {', '.join(impacted_sites)}"
            )

            # Check if incident is already logged
            existing = self.db.query(Incident).filter(
                Incident.status == "open",
                Incident.root_cause_device_id == rc_id,
                Incident.root_cause_type == "topological_outage"
            ).first()

            if not existing:
                new_inc = Incident(
                    title=title,
                    description=description,
                    severity=severity,
                    status="open",
                    root_cause_device_id=rc_id,
                    root_cause_type="topological_outage",
                    impacted_services={
                        "affected_count": len(affected_hostnames),
                        "affected_hostnames": affected_hostnames,
                        "sites": impacted_sites
                    }
                )
                self.db.add(new_inc)
                consolidated_alerts.append(new_inc)
                logger.warning(f"[RCA Engine] Consolidated ticket created for root-cause {rc_device.hostname}")
            else:
                # Update existing ticket impact
                existing.description = description
                existing.severity = severity
                existing.impacted_services = {
                    "affected_count": len(affected_hostnames),
                    "affected_hostnames": affected_hostnames,
                    "sites": impacted_sites
                }
                consolidated_alerts.append(existing)

        self.db.commit()
        return {
            "status": "completed",
            "root_causes": [
                {
                    "device_id": str(r_id),
                    "device_name": device_map[r_id].hostname,
                    "affected_downstream_count": len(root_causes.get(r_id, []))
                }
                for r_id in independent_failures.union(root_causes.keys())
            ]
        }
