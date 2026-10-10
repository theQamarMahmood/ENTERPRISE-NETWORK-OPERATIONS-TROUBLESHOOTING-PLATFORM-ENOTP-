import uuid
from sqlalchemy import Column, String, Integer, BigInteger, Float, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True)
    role = Column(String(50), nullable=False) # admin, senior_engineer, engineer, noc, security, auditor
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Device(Base):
    __tablename__ = "devices"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    hostname = Column(String(255), unique=True, nullable=False, index=True)
    ip_address = Column(String(45), unique=True, nullable=False, index=True)
    mac_address = Column(String(17), unique=True, index=True)
    vendor = Column(String(100))
    model = Column(String(100))
    product_family = Column(String(100))
    serial_number = Column(String(100), unique=True, index=True)
    os_version = Column(String(100))
    hardware_version = Column(String(100))
    device_type = Column(String(50), nullable=False, index=True)  # router, switch, firewall, server, ap, phone, printer, etc.
    site = Column(String(100), nullable=False, index=True)
    building = Column(String(100))
    rack = Column(String(100))
    vlan_id = Column(Integer)
    
    # Switch Port mappings
    connected_switch_id = Column(String(36), ForeignKey("devices.id", ondelete="SET NULL"))
    connected_port = Column(String(100))
    
    uptime = Column(BigInteger, default=0)
    license_info = Column(JSON, default=dict)
    eol_status = Column(String(50))
    eos_status = Column(String(50))
    status = Column(String(20), default="unknown", index=True)  # online, offline, degraded, unknown
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # SNMP Configuration (stored locally and encrypted)
    snmp_version = Column(String(10), default="v2c") # v2c or v3
    snmp_community_encrypted = Column(String(255))
    snmp_v3_user = Column(String(100))
    snmp_v3_auth_key = Column(String(255))
    snmp_v3_priv_key = Column(String(255))

    # SSH Connection Details
    ssh_username = Column(String(100))
    ssh_password_encrypted = Column(String(255))
    ssh_key_encrypted = Column(Text)

    # Relationships
    interfaces = relationship("Interface", back_populates="device", cascade="all, delete-orphan")
    tunnels = relationship("Tunnel", back_populates="device", cascade="all, delete-orphan")
    routes = relationship("Route", back_populates="device", cascade="all, delete-orphan")
    config_backups = relationship("ConfigurationBackup", back_populates="device", cascade="all, delete-orphan")


class Interface(Base):
    __tablename__ = "interfaces"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False, index=True)
    description = Column(String(255))
    status = Column(String(10), nullable=False)  # up, down, admin_down
    mac_address = Column(String(17))
    ip_address = Column(String(45))
    subnet_mask = Column(String(45))
    vlan_id = Column(Integer)
    speed = Column(String(20))
    duplex = Column(String(20))
    mtu = Column(Integer)
    
    # SNMP Metrics
    in_octets = Column(BigInteger, default=0)
    out_octets = Column(BigInteger, default=0)
    in_errors = Column(BigInteger, default=0)
    out_errors = Column(BigInteger, default=0)
    crc_errors = Column(BigInteger, default=0)
    collisions = Column(BigInteger, default=0)
    drops = Column(BigInteger, default=0)
    
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    device = relationship("Device", back_populates="interfaces")


class Tunnel(Base):
    __tablename__ = "tunnels"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False, index=True)
    tunnel_type = Column(String(50), nullable=False)  # IPsec, GRE, DMVPN, SSL VPN, SD-WAN
    local_ip = Column(String(45), nullable=False)
    remote_ip = Column(String(45), nullable=False)
    status = Column(String(20), default="down")
    phase_1_status = Column(String(50))
    phase_2_status = Column(String(50))
    encryption_algorithm = Column(String(50))
    latency_ms = Column(Float, default=0.0)
    packet_loss_pct = Column(Float, default=0.0)
    jitter_ms = Column(Float, default=0.0)
    rekey_time = Column(DateTime(timezone=True))
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    device = relationship("Device", back_populates="tunnels")


class Route(Base):
    __tablename__ = "routes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    destination = Column(String(45), nullable=False, index=True)
    netmask = Column(String(45))
    next_hop = Column(String(45))
    interface = Column(String(100))
    protocol = Column(String(50), nullable=False)  # static, ospf, eigrp, bgp, connected
    metric = Column(Integer)
    preference = Column(Integer)
    status = Column(String(20), default="active")

    device = relationship("Device", back_populates="routes")


class TopologyLink(Base):
    __tablename__ = "topology_links"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_device_id = Column(String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    source_interface = Column(String(100), nullable=False)
    target_device_id = Column(String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    target_interface = Column(String(100), nullable=False)
    link_type = Column(String(20), nullable=False)  # physical, logical_tunnel, parent_child
    discovery_protocol = Column(String(20))  # cdp, lldp, arp, static
    last_verified = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    description = Column(Text)
    severity = Column(String(20), nullable=False, index=True)  # critical, major, minor, warning
    status = Column(String(20), default="open", index=True)  # open, acknowledged, resolved
    root_cause_device_id = Column(String(36), ForeignKey("devices.id", ondelete="SET NULL"))
    root_cause_type = Column(String(100))
    impacted_services = Column(JSON, default=dict)  # list of affected offices, VLANs, users, tunnels
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True))


class ConfigurationBackup(Base):
    __tablename__ = "configuration_backups"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    config_text = Column(Text, nullable=False)
    checksum = Column(String(64), nullable=False)
    version = Column(Integer, nullable=False)
    created_by = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    device = relationship("Device", back_populates="config_backups")


class SyslogRecord(Base):
    __tablename__ = "syslogs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_ip = Column(String(45), nullable=False, index=True)
    hostname = Column(String(255), index=True)
    facility = Column(String(50))
    severity = Column(String(20), nullable=False, index=True)  # emergency, alert, critical, error, warning, notice, info, debug
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    message = Column(Text, nullable=False)
    parsed_event_type = Column(String(100), index=True)  # link_down, config_change, auth_failure, etc.
    correlated_incident_id = Column(String(36), ForeignKey("incidents.id", ondelete="SET NULL"))


class FlowRecord(Base):
    __tablename__ = "flow_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_ip = Column(String(45), nullable=False, index=True)
    destination_ip = Column(String(45), nullable=False, index=True)
    source_port = Column(Integer, nullable=False)
    destination_port = Column(Integer, nullable=False)
    protocol = Column(Integer, nullable=False)  # 6=TCP, 17=UDP, 1=ICMP, etc.
    octets = Column(BigInteger, default=0)
    packets = Column(BigInteger, default=0)
    start_time = Column(DateTime(timezone=True), index=True)
    end_time = Column(DateTime(timezone=True))
