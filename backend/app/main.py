import asyncio
import logging
from typing import List, Dict, Any
from uuid import UUID
from datetime import datetime
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import Base, sync_engine, get_db, get_sync_db, SessionLocalSync
from app.models.models import Device, Interface, Route, Tunnel, TopologyLink, Incident, SyslogRecord, FlowRecord, User
from app.schemas import schemas
from app.services.discovery import DiscoveryService
from app.services.snmp_poller import SNMPPoller
from app.services.syslog_server import SyslogServer
from app.services.flow_collector import NetFlowCollector
from app.services.rca_engine import RCAEngine
from app.services.digital_twin import DigitalTwinSimulator
from app.services.config_manager import ConfigurationManager

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ENOTP_Core")

# Background Services Store
syslog_daemon = None
netflow_daemon = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown events for UDP services and database initialization."""
    global syslog_daemon, netflow_daemon
    
    # 1. Create database tables if they do not exist
    Base.metadata.create_all(bind=sync_engine)
    logger.info("Database schemas verified/created.")

    # 2. Seed mock network data for development validation
    _seed_mock_data()

    # 3. Start Passive Daemons
    syslog_daemon = SyslogServer()
    syslog_daemon.start()
    
    netflow_daemon = NetFlowCollector()
    netflow_daemon.start()
    
    yield
    
    # 4. Clean up Passive Daemons on shutdown
    if syslog_daemon:
        syslog_daemon.stop()
    if netflow_daemon:
        netflow_daemon.stop()

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan
)

# CORS Middleware (React Dashboard Support)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

ws_manager = ConnectionManager()

# WebSocket Endpoint
@app.websocket("/api/v1/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

# ----------------- REST ROUTERS -----------------

@app.get("/api/v1/dashboard/metrics", response_model=schemas.DashboardMetrics)
def get_dashboard_metrics(db = Depends(get_sync_db)):
    """Aggregates all real-time stats for the NOC single-pane of glass dashboard."""
    # Count totals
    total_devs = db.query(Device).count()
    online_devs = db.query(Device).filter(Device.status == "online").count()
    offline_devs = db.query(Device).filter(Device.status == "offline").count()

    active_incidents = db.query(Incident).filter(Incident.status == "open").count()
    critical_alerts = db.query(Incident).filter(Incident.status == "open", Incident.severity == "critical").count()

    # Calculate status sums
    tunnels_up = db.query(Tunnel).filter(Tunnel.status == "up").count()
    tunnels_down = db.query(Tunnel).filter(Tunnel.status == "down").count()

    # Top bandwidth consumers (NetFlow Aggregation Mock)
    top_bandwidth = [
        {"ip": "192.168.1.100", "hostname": "Eng-Workstation-01", "bandwidth_mbps": 42.5, "protocol": "HTTPS"},
        {"ip": "192.168.1.50", "hostname": "Local-Backup-NAS", "bandwidth_mbps": 28.1, "protocol": "TCP Backup"},
        {"ip": "10.0.0.12", "hostname": "Prod-DB-Primary", "bandwidth_mbps": 18.3, "protocol": "PostgreSQL"},
    ]

    return {
        "network_health_score": 100 - (active_incidents * 15) if total_devs > 0 else 100,
        "routing_health": 95 if active_incidents == 0 else 80,
        "switching_health": 98 if offline_devs == 0 else 85,
        "vpn_health": 100 if tunnels_down == 0 else 70,
        "wan_health": 99,
        "security_health": 100,
        "total_devices": total_devs,
        "online_devices": online_devs,
        "offline_devices": offline_devs,
        "critical_alerts": critical_alerts,
        "active_incidents": active_incidents,
        "root_causes": [
            {"device": "Dist-Switch-02", "reason": "STP Loop / High CPU", "impact": "Site B isolated"}
        ] if offline_devs > 0 else [],
        "tunnel_status": {"up": tunnels_up, "down": tunnels_down},
        "isp_status": {"primary_latency_ms": 12.4, "primary_loss_pct": 0.0, "status": "active"},
        "top_bandwidth_consumers": top_bandwidth
    }

@app.get("/api/v1/devices", response_model=List[schemas.DeviceResponse])
def list_devices(db = Depends(get_sync_db)):
    return db.query(Device).all()

@app.get("/api/v1/devices/{device_id}", response_model=schemas.DeviceDetailedResponse)
def get_device_details(device_id: str, db = Depends(get_sync_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found.")
    return device

@app.post("/api/v1/devices", response_model=schemas.DeviceResponse)
def create_device(device_in: schemas.DeviceCreate, db = Depends(get_sync_db)):
    import datetime as _dt
    # Build device with explicit Python-side defaults for server_default columns
    device = Device(
        hostname=device_in.hostname,
        ip_address=device_in.ip_address,
        mac_address=device_in.mac_address,
        vendor=device_in.vendor,
        model=device_in.model,
        device_type=device_in.device_type,
        site=device_in.site,
        building=device_in.building,
        rack=device_in.rack,
        vlan_id=device_in.vlan_id,
        snmp_version=device_in.snmp_version or "v2c",
        snmp_v3_user=device_in.snmp_v3_user,
        # Explicit defaults so Pydantic validation never sees None
        status="unknown",
        uptime=0,
        last_seen=_dt.datetime.utcnow(),
    )
    db.add(device)
    db.commit()
    db.expire(device)  # Force SQLAlchemy to reload all columns from DB
    db.refresh(device)
    return device

@app.post("/api/v1/devices/{device_id}/poll")
async def force_poll_device(device_id: str, db: Session = Depends(get_db)):
    """Triggers an active SNMP poll on the device immediately."""
    poller = SNMPPoller(db)
    success = await poller.poll_device(device_id)
    if not success:
        raise HTTPException(status_code=500, detail="SNMP Poll failed.")
    return {"status": "success", "message": "Device successfully polled."}

@app.post("/api/v1/devices/{device_id}/backup")
def backup_config(device_id: str, db = Depends(get_sync_db)):
    manager = ConfigurationManager(db)
    success, message = manager.backup_device_config(device_id, "Admin Operator")
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"status": "success", "message": message}

@app.get("/api/v1/devices/{device_id}/configs", response_model=List[schemas.ConfigBackupResponse])
def get_config_backups(device_id: str, db = Depends(get_sync_db)):
    return db.query(ConfigurationBackup).filter(ConfigurationBackup.device_id == device_id).order_by(ConfigurationBackup.version.desc()).all()

@app.get("/api/v1/devices/{device_id}/configs/{version}", response_model=schemas.ConfigBackupDetailed)
def get_config_backup_version(device_id: str, version: int, db = Depends(get_sync_db)):
    backup = db.query(ConfigurationBackup).filter(
        ConfigurationBackup.device_id == device_id,
        ConfigurationBackup.version == version
    ).first()
    if not backup:
        raise HTTPException(status_code=404, detail="Configuration version not found.")
    return backup

@app.get("/api/v1/devices/{device_id}/configs/compare/{ver_a}/{ver_b}", response_model=schemas.ConfigCompareResponse)
def compare_configs(device_id: str, ver_a: int, ver_b: int, db = Depends(get_sync_db)):
    manager = ConfigurationManager(db)
    success, diff_result = manager.compare_configurations(device_id, ver_a, ver_b)
    if not success:
        raise HTTPException(status_code=400, detail=diff_result)
    return {"version_a": ver_a, "version_b": ver_b, "diff": diff_result}

@app.post("/api/v1/devices/{device_id}/rollback/{version}")
def rollback_config(device_id: str, version: int, db = Depends(get_sync_db)):
    manager = ConfigurationManager(db)
    success, message = manager.rollback_configuration(device_id, version)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"status": "success", "message": message}

# ----------------- INTEL ENGINES -----------------

@app.post("/api/v1/twin/simulate-link-shutdown")
def simulate_twin_link_down(source: str, target: str, db = Depends(get_sync_db)):
    simulator = DigitalTwinSimulator(db)
    result = simulator.simulate_link_shutdown(source, target)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/api/v1/twin/simulate-metric-change")
def simulate_twin_metric_change(source: str, target: str, metric: int, db = Depends(get_sync_db)):
    simulator = DigitalTwinSimulator(db)
    result = simulator.simulate_routing_metric_change(source, target, metric)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/api/v1/twin/simulate-acl-change")
def simulate_twin_acl_change(src_subnet: str, dst_subnet: str, port: int, action: str, db = Depends(get_sync_db)):
    simulator = DigitalTwinSimulator(db)
    return simulator.simulate_firewall_policy_change(src_subnet, dst_subnet, port, action)

@app.post("/api/v1/rca/trigger")
def trigger_rca(db = Depends(get_sync_db)):
    rca = RCAEngine(db)
    return rca.run_root_cause_analysis()

@app.get("/api/v1/incidents", response_model=List[schemas.IncidentResponse])
def get_incidents(db = Depends(get_sync_db)):
    return db.query(Incident).order_by(Incident.created_at.desc()).all()

@app.get("/api/v1/topology", response_model=List[schemas.TopologyLinkResponse])
def get_topology_links(db = Depends(get_sync_db)):
    return db.query(TopologyLink).all()

# ----------------- MOCK DATA SEEDING -----------------

def _seed_mock_data():
    """Seeds the DB with dummy routers, switches, firewalls, and links for immediate visual UI testing."""
    db = SessionLocalSync()
    try:
        # Check if users/devices exist
        if db.query(Device).count() > 0:
            return

        # 1. Create Admin User
        from app.core.security import get_password_hash
        admin = User(
            username="admin",
            password_hash=get_password_hash("admin123"),
            email="admin@enterprise.net",
            role="admin",
            is_active=True
        )
        db.add(admin)

        # 2. Add devices
        core_switch = Device(
            hostname="Core-Switch-01",
            ip_address="10.0.0.1",
            mac_address="00:1d:a1:00:00:01",
            device_type="switch",
            site="Headquarters",
            vendor="Cisco",
            model="Catalyst 9500",
            status="online"
        )
        dist_switch_1 = Device(
            hostname="Dist-Switch-01",
            ip_address="10.0.0.2",
            mac_address="00:1d:a1:00:00:02",
            device_type="switch",
            site="Headquarters",
            vendor="Cisco",
            model="Catalyst 9300",
            status="online"
        )
        dist_switch_2 = Device(
            hostname="Dist-Switch-02",
            ip_address="10.0.0.3",
            mac_address="00:1d:a1:00:00:03",
            device_type="switch",
            site="Branch Office A",
            vendor="Cisco",
            model="Catalyst 9300",
            status="offline" # Seed one offline to demonstrate Root Cause topological logic
        )
        border_router = Device(
            hostname="Border-Router-01",
            ip_address="192.168.1.1",
            mac_address="00:1d:a1:00:00:04",
            device_type="router",
            site="Headquarters",
            vendor="Juniper",
            model="MX240",
            status="online"
        )
        firewall = Device(
            hostname="FW-Edge-01",
            ip_address="192.168.1.2",
            mac_address="00:1d:a1:00:00:05",
            device_type="firewall",
            site="Headquarters",
            vendor="Fortinet",
            model="FortiGate 100F",
            status="online"
        )
        db.add_all([core_switch, dist_switch_1, dist_switch_2, border_router, firewall])
        db.flush()

        # 3. Create Links
        links = [
            TopologyLink(source_device_id=core_switch.id, source_interface="TenGig1/0/1", target_device_id=dist_switch_1.id, target_interface="Gig1/0/48", link_type="physical", discovery_protocol="lldp"),
            TopologyLink(source_device_id=core_switch.id, source_interface="TenGig1/0/2", target_device_id=dist_switch_2.id, target_interface="Gig1/0/48", link_type="physical", discovery_protocol="lldp"),
            TopologyLink(source_device_id=core_switch.id, source_interface="Gig0/0", target_device_id=border_router.id, target_interface="ge-0/0/0", link_type="physical", discovery_protocol="cdp"),
            TopologyLink(source_device_id=border_router.id, source_interface="ge-0/0/1", target_device_id=firewall.id, target_interface="port1", link_type="physical", discovery_protocol="static")
        ]
        db.add_all(links)

        # 4. Create Incident for Offline Switch
        incident = Incident(
            title="Switch Offline - Dist-Switch-02",
            description="Branch Access Distribution switch went offline. Neighbor OSPF adjacency down.",
            severity="critical",
            status="open",
            root_cause_device_id=dist_switch_2.id,
            root_cause_type="icmp_failure"
        )
        db.add(incident)
        db.commit()
        logger.info("Mock database seed finished successfully.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding mock database: {e}")
    finally:
        db.close()
