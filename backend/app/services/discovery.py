import sys
import subprocess
import re
import socket
import asyncio
from typing import List, Dict, Any, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.models import Device, Interface
from app.core.security import decrypt_credential

# Subprocess-based ping that works across Windows and Linux
def ping_ip(ip: str, timeout_ms: int = 500) -> bool:
    """Run a single ping to an IP address. Safe on Windows and Linux."""
    if sys.platform == "win32":
        # Windows ping command
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), ip]
    else:
        # Linux/macOS ping command
        cmd = ["ping", "-c", "1", "-W", str(timeout_ms // 1000 or 1), ip]
    
    try:
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.0)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False

def get_mac_from_arp(ip: str) -> Optional[str]:
    """Retrieves MAC address for a given IP from local ARP cache."""
    try:
        if sys.platform == "win32":
            # Run arp -a on Windows
            output = subprocess.check_output(["arp", "-a", ip], stderr=subprocess.DEVNULL).decode(errors="ignore")
            # Regex for IP and MAC matches
            # Matches IP followed by spaces followed by MAC (XX-XX-XX-XX-XX-XX)
            mac_match = re.search(r"([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}", output)
            if mac_match:
                return mac_match.group(0).replace("-", ":").lower()
        else:
            # Linux arp
            output = subprocess.check_output(["arp", "-n", ip], stderr=subprocess.DEVNULL).decode(errors="ignore")
            mac_match = re.search(r"([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}", output)
            if mac_match:
                return mac_match.group(0).lower()
    except Exception:
        pass
    return None

def resolve_hostname(ip: str) -> str:
    """Perform reverse DNS query to retrieve hostname."""
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return hostname
    except Exception:
        return f"dev-{ip.replace('.', '-')}"

class DiscoveryService:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.thread_pool = ThreadPoolExecutor(max_workers=50)

    async def scan_subnet(self, subnet: str) -> List[Dict[str, Any]]:
        """Scans a subnet (e.g. 192.168.1.0/24) and identifies online hosts, hostnames, and MACs."""
        # Clean the subnet string (handling simple ranges/CIDR)
        # For a production app, we would use ipaddress module to parse CIDR
        import ipaddress
        try:
            net = ipaddress.ip_network(subnet, strict=False)
            hosts = [str(ip) for ip in net.hosts()]
        except Exception as e:
            print(f"Error parsing subnet {subnet}: {e}")
            return []

        loop = asyncio.get_event_loop()
        futures = []
        for ip in hosts:
            futures.append(loop.run_in_executor(self.thread_pool, ping_ip, ip))
        
        results = await asyncio.gather(*futures)
        
        online_hosts = []
        for ip, is_online in zip(hosts, results):
            if is_online:
                # Resolve MAC & Hostname asynchronously
                mac = await loop.run_in_executor(self.thread_pool, get_mac_from_arp, ip)
                hostname = await loop.run_in_executor(self.thread_pool, resolve_hostname, ip)
                online_hosts.append({
                    "ip_address": ip,
                    "mac_address": mac,
                    "hostname": hostname
                })
        
        return online_hosts

    def update_discovered_devices(self, discovered_hosts: List[Dict[str, Any]], site: str = "Primary Site"):
        """Updates or registers newly discovered hosts in the database."""
        for host in discovered_hosts:
            ip = host["ip_address"]
            mac = host["mac_address"]
            hostname = host["hostname"]

            # Query existing device
            device = self.db.query(Device).filter((Device.ip_address == ip) | (Device.mac_address == mac)).first()
            
            if not device:
                # New device detected
                new_device = Device(
                    hostname=hostname,
                    ip_address=ip,
                    mac_address=mac,
                    device_type="unknown",
                    status="online",
                    site=site,
                    vendor="Unknown",
                    model="Unknown Model"
                )
                self.db.add(new_device)
                self.db.flush() # Generate ID for logging/new device detection triggers
                print(f"[NDDE] Detected new device: {hostname} ({ip} / {mac})")
                # Trigger callback or broadcast for New Device popup
            else:
                # Update status
                device.status = "online"
                device.last_seen = func.now()
        
        self.db.commit()
