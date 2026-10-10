from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

# Token & Auth Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    email: EmailStr
    role: str # admin, senior_engineer, engineer, noc, security, auditor

class UserResponse(BaseModel):
    id: UUID
    username: str
    email: Optional[str]
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Interface Schemas
class InterfaceBase(BaseModel):
    name: str
    description: Optional[str] = None
    status: str
    mac_address: Optional[str] = None
    ip_address: Optional[str] = None
    subnet_mask: Optional[str] = None
    vlan_id: Optional[int] = None
    speed: Optional[str] = None
    duplex: Optional[str] = None
    mtu: Optional[int] = None

class InterfaceResponse(InterfaceBase):
    id: UUID
    device_id: UUID
    in_octets: int
    out_octets: int
    in_errors: int
    out_errors: int
    crc_errors: int
    collisions: int
    drops: int
    last_updated: datetime

    class Config:
        from_attributes = True

# Tunnel Schemas
class TunnelBase(BaseModel):
    name: str
    tunnel_type: str
    local_ip: str
    remote_ip: str
    status: str
    phase_1_status: Optional[str] = None
    phase_2_status: Optional[str] = None
    encryption_algorithm: Optional[str] = None

class TunnelResponse(TunnelBase):
    id: UUID
    device_id: UUID
    latency_ms: float
    packet_loss_pct: float
    jitter_ms: float
    rekey_time: Optional[datetime] = None
    last_updated: datetime

    class Config:
        from_attributes = True

# Route Schemas
class RouteBase(BaseModel):
    destination: str
    netmask: Optional[str] = None
    next_hop: Optional[str] = None
    interface: Optional[str] = None
    protocol: str
    metric: Optional[int] = None
    preference: Optional[int] = None
    status: str

class RouteResponse(RouteBase):
    id: UUID
    device_id: UUID

    class Config:
        from_attributes = True

# Device Schemas
class DeviceBase(BaseModel):
    hostname: str
    ip_address: str
    mac_address: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    product_family: Optional[str] = None
    serial_number: Optional[str] = None
    os_version: Optional[str] = None
    hardware_version: Optional[str] = None
    device_type: str
    site: str
    building: Optional[str] = None
    rack: Optional[str] = None
    vlan_id: Optional[int] = None
    connected_switch_id: Optional[UUID] = None
    connected_port: Optional[str] = None

class DeviceCreate(DeviceBase):
    snmp_version: Optional[str] = "v2c"
    snmp_community: Optional[str] = None
    snmp_v3_user: Optional[str] = None
    snmp_v3_auth_key: Optional[str] = None
    snmp_v3_priv_key: Optional[str] = None
    ssh_username: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_private_key: Optional[str] = None

class DeviceResponse(DeviceBase):
    id: UUID
    status: str
    uptime: int
    eol_status: Optional[str] = None
    eos_status: Optional[str] = None
    last_seen: datetime

    class Config:
        from_attributes = True

class DeviceDetailedResponse(DeviceResponse):
    interfaces: List[InterfaceResponse] = []
    tunnels: List[TunnelResponse] = []
    routes: List[RouteResponse] = []

    class Config:
        from_attributes = True

# Incident Schemas
class IncidentBase(BaseModel):
    title: str
    description: Optional[str] = None
    severity: str
    status: str = "open"
    root_cause_device_id: Optional[UUID] = None
    root_cause_type: Optional[str] = None
    impacted_services: Dict[str, Any] = Field(default_factory=dict)

class IncidentCreate(IncidentBase):
    pass

class IncidentUpdate(BaseModel):
    status: Optional[str] = None
    severity: Optional[str] = None
    root_cause_device_id: Optional[UUID] = None
    root_cause_type: Optional[str] = None
    resolved_at: Optional[datetime] = None

class IncidentResponse(IncidentBase):
    id: UUID
    created_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Topology Link Schema
class TopologyLinkResponse(BaseModel):
    id: UUID
    source_device_id: UUID
    source_interface: str
    target_device_id: UUID
    target_interface: str
    link_type: str
    discovery_protocol: Optional[str] = None
    last_verified: datetime

    class Config:
        from_attributes = True

# Config Management Schemas
class ConfigBackupResponse(BaseModel):
    id: UUID
    device_id: UUID
    checksum: str
    version: int
    created_by: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ConfigBackupDetailed(ConfigBackupResponse):
    config_text: str

    class Config:
        from_attributes = True

class ConfigCompareResponse(BaseModel):
    version_a: int
    version_b: int
    diff: str

# Syslog & Flow Schemas
class SyslogResponse(BaseModel):
    id: UUID
    device_ip: str
    hostname: Optional[str] = None
    facility: Optional[str] = None
    severity: str
    timestamp: datetime
    message: str
    parsed_event_type: Optional[str] = None

    class Config:
        from_attributes = True

class FlowResponse(BaseModel):
    id: UUID
    source_ip: str
    destination_ip: str
    source_port: int
    destination_port: int
    protocol: int
    octets: int
    packets: int
    start_time: datetime
    end_time: Optional[datetime] = None

    class Config:
        from_attributes = True

# Dashboard Metrics
class DashboardMetrics(BaseModel):
    network_health_score: int
    routing_health: int
    switching_health: int
    vpn_health: int
    wan_health: int
    security_health: int
    total_devices: int
    online_devices: int
    offline_devices: int
    critical_alerts: int
    active_incidents: int
    root_causes: List[Dict[str, Any]]
    tunnel_status: Dict[str, int]
    isp_status: Dict[str, Any]
    top_bandwidth_consumers: List[Dict[str, Any]]
