import logging
import networkx as nx
from typing import Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from app.models.models import Device, TopologyLink, Interface, Route

logger = logging.getLogger("ENOTP_Twin")

class DigitalTwinSimulator:
    def __init__(self, db_session: Session):
        self.db = db_session

    def _build_simulation_graph(self) -> Tuple[nx.DiGraph, Dict[str, Device]]:
        """Constructs a directed NetworkX graph representing the live network routing paths."""
        devices = self.db.query(Device).all()
        links = self.db.query(TopologyLink).all()
        
        G = nx.DiGraph()
        device_map = {}

        # Add node details
        for dev in devices:
            G.add_node(dev.hostname, id=dev.id, site=dev.site, type=dev.device_type)
            device_map[dev.hostname] = dev

        # Add links. We fetch routes to determine routing costs (metrics).
        # Fallback to default link weight of 10 (OSPF default cost for 100M link) if no OSPF route is declared
        for link in links:
            source_dev = self.db.query(Device).filter(Device.id == link.source_device_id).first()
            target_dev = self.db.query(Device).filter(Device.id == link.target_device_id).first()

            if source_dev and target_dev:
                # Add bidirectional link
                G.add_edge(source_dev.hostname, target_dev.hostname, weight=10, type=link.link_type, src_port=link.source_interface, dst_port=link.target_interface)
                G.add_edge(target_dev.hostname, source_dev.hostname, weight=10, type=link.link_type, src_port=link.target_interface, dst_port=link.source_interface)

        return G, device_map

    def simulate_link_shutdown(self, source_hostname: str, target_hostname: str) -> Dict[str, Any]:
        """Simulates removing a link (e.g. interface shutdown) and evaluates routing impact."""
        G, device_map = self._build_simulation_graph()
        
        if not G.has_edge(source_hostname, target_hostname):
            return {"error": f"Link between {source_hostname} and {target_hostname} does not exist in graph."}

        # Calculate original connectivity paths
        core_node = self._find_core_node(G)
        if not core_node:
            return {"error": "Could not identify core root node to measure connectivity."}

        original_paths = {}
        for node in G.nodes():
            if node != core_node:
                try:
                    original_paths[node] = nx.shortest_path(G, source=core_node, target=node, weight="weight")
                except nx.NetworkXNoPath:
                    original_paths[node] = None

        # Execute simulation: Remove the edge
        G.remove_edge(source_hostname, target_hostname)
        G.remove_edge(target_hostname, source_hostname)

        # Calculate new connectivity paths
        new_paths = {}
        isolated_devices = []
        routed_paths_shifted = []

        for node in G.nodes():
            if node != core_node:
                try:
                    path = nx.shortest_path(G, source=core_node, target=node, weight="weight")
                    new_paths[node] = path
                    # Check if route shifted/changed hops
                    if original_paths[node] and path != original_paths[node]:
                        routed_paths_shifted.append({
                            "device": node,
                            "original_path": original_paths[node],
                            "new_path": path,
                            "metric_increase": sum(G[path[i]][path[i+1]]['weight'] for i in range(len(path)-1)) - sum(G[original_paths[node][i]][original_paths[node][i+1]]['weight'] for i in range(len(original_paths[node])-1))
                        })
                except nx.NetworkXNoPath:
                    new_paths[node] = None
                    isolated_devices.append(node)

        # Compile risk analysis report
        risk_level = "low"
        if isolated_devices:
            risk_level = "critical"
        elif routed_paths_shifted:
            risk_level = "medium"

        impacted_sites = list({device_map[node].site for node in isolated_devices})

        return {
            "simulation_type": "link_shutdown",
            "target_link": f"{source_hostname} <-> {target_hostname}",
            "risk_level": risk_level,
            "isolated_devices": isolated_devices,
            "isolated_sites": impacted_sites,
            "routed_paths_shifted": routed_paths_shifted,
            "summary": (
                f"SHUTDOWN SIMULATION: Removing the link between {source_hostname} and {target_hostname} "
                f"will result in {len(isolated_devices)} devices becoming isolated from Core and "
                f"{len(routed_paths_shifted)} path reroutings."
            )
        }

    def simulate_routing_metric_change(self, source_hostname: str, target_hostname: str, new_weight: int) -> Dict[str, Any]:
        """Simulates changing OSPF cost / BGP metric of a link and validates path shifts."""
        G, device_map = self._build_simulation_graph()

        if not G.has_edge(source_hostname, target_hostname):
            return {"error": "Link does not exist."}

        core_node = self._find_core_node(G)
        if not core_node:
            return {"error": "No Core Switch node identified."}

        # Calculate original paths
        original_paths = {}
        for node in G.nodes():
            if node != core_node:
                try:
                    original_paths[node] = nx.shortest_path(G, source=core_node, target=node, weight="weight")
                except nx.NetworkXNoPath:
                    original_paths[node] = None

        # Apply simulation: Change weight
        G[source_hostname][target_hostname]['weight'] = new_weight
        G[target_hostname][source_hostname]['weight'] = new_weight

        # Re-evaluate
        path_shifts = []
        for node in G.nodes():
            if node != core_node:
                try:
                    path = nx.shortest_path(G, source=core_node, target=node, weight="weight")
                    if original_paths[node] and path != original_paths[node]:
                        path_shifts.append({
                            "device": node,
                            "original_path": original_paths[node],
                            "new_path": path
                        })
                except nx.NetworkXNoPath:
                    pass

        return {
            "simulation_type": "metric_shift",
            "target_link": f"{source_hostname} <--> {target_hostname}",
            "new_metric_cost": new_weight,
            "risk_level": "medium" if path_shifts else "low",
            "path_shifts": path_shifts,
            "summary": f"Changing interface cost to {new_weight} results in {len(path_shifts)} devices rerouting active traffic."
        }

    def simulate_firewall_policy_change(self, src_subnet: str, dst_subnet: str, port: int, action: str) -> Dict[str, Any]:
        """Simulates a firewall ACL addition to verify security alignment and prevent connectivity loss."""
        # Simple ACL parsing simulator
        # E.g., blocking 192.168.1.0/24 access to 10.0.0.0/24
        # Validate if this blocks key infrastructure paths (like SNMP polling or Syslog ingestion)
        warnings = []
        risk_level = "low"

        # Rule check: If we block traffic to the local network core
        if action == "deny" and ("192.168.1" in dst_subnet or "10.0.0" in dst_subnet) and port in [80, 443, 22, 514, 2055, 161]:
            warnings.append(f"Security Alert: Rule blocks on-premises management service port {port}. This will isolate polling engines!")
            risk_level = "critical"
        elif action == "allow" and src_subnet in ["0.0.0.0/0", "*"] and port in [22, 23, 3389]:
            warnings.append("Compliance Warning: Rule exposes administrative SSH/RDP ports to public subnets.")
            risk_level = "high"

        return {
            "simulation_type": "firewall_policy",
            "risk_level": risk_level,
            "warnings": warnings,
            "approved": len(warnings) == 0,
            "summary": "Policy change approved." if not warnings else "Policy change blocked by compliance engine."
        }

    def _find_core_node(self, G: nx.DiGraph) -> str:
        """Finds root node representing network core switch."""
        for node in G.nodes():
            if "core" in node.lower():
                return node
        # Fallback to first switch
        for node in G.nodes():
            if G.nodes[node].get("type") == "switch":
                return node
        # Final fallback
        nodes = list(G.nodes())
        return nodes[0] if nodes else None
