import socket
import struct
import threading
import logging
import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.core.database import SessionLocalSync
from app.models.models import FlowRecord
from app.core.config import settings

logger = logging.getLogger("ENOTP_NetFlow")

class NetFlowCollector:
    def __init__(self, host: str = "0.0.0.0", port: int = None):
        self.host = host
        self.port = port or settings.NETFLOW_PORT
        self.socket = None
        self.running = False
        self.thread = None

    def start(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind((self.host, self.port))
            self.running = True
            self.thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.thread.start()
            logger.info(f"NetFlow collector listening on {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to start NetFlow collector on port {self.port}: {e}")

    def stop(self):
        self.running = False
        if self.socket:
            self.socket.close()
        if self.thread:
            self.thread.join(timeout=2.0)
        logger.info("NetFlow collector stopped.")

    def _listen_loop(self):
        while self.running:
            try:
                data, addr = self.socket.recvfrom(8192)
                self._parse_netflow(data, addr[0])
            except Exception as e:
                if self.running:
                    logger.error(f"Error in NetFlow listen loop: {e}")

    def _parse_netflow(self, data: bytes, exporter_ip: str):
        """Parses basic NetFlow v5 header and records."""
        db = SessionLocalSync()
        try:
            if len(data) < 24:
                return

            # NetFlow v5 Header format (Big Endian):
            # version (2B), count (2B), sys_uptime (4B), unix_secs (4B), unix_nsecs (4B),
            # flow_sequence (4B), engine_type (1B), engine_id (1B), sampling_interval (2B)
            version, count = struct.unpack("!HH", data[:4])

            if version != 5:
                # In production, we would also parse NetFlow v9 / IPFIX templates
                return

            offset = 24
            record_size = 48
            records_parsed = 0

            # Parse up to the count specified in header
            for _ in range(count):
                if len(data) < offset + record_size:
                    break

                # NetFlow v5 Record format:
                # srcaddr (4B), dstaddr (4B), nexthop (4B), input (2B), output (2B),
                # dPkts (4B), dOctets (4B), first (4B), last (4B), srcport (2B), dstport (2B),
                # pad1 (1B), tcp_flags (1B), prot (1B), tos (1B), src_as (2B), dst_as (2B),
                # src_mask (1B), dst_mask (1B), pad2 (2B)
                src_ip_raw, dst_ip_raw, _, _, _, packets, octets, _, _, src_port, dst_port, _, _, proto, *_ = struct.unpack(
                    "!IIIHHIIIIHHBBHHiBBH", data[offset:offset+record_size]
                )

                src_ip = socket.inet_ntoa(struct.pack("!I", src_ip_raw))
                dst_ip = socket.inet_ntoa(struct.pack("!I", dst_ip_raw))

                flow_rec = FlowRecord(
                    source_ip=src_ip,
                    destination_ip=dst_ip,
                    source_port=src_port,
                    destination_port=dst_port,
                    protocol=proto,
                    octets=octets,
                    packets=packets,
                    start_time=datetime.now() - timedelta(seconds=5),
                    end_time=datetime.now()
                )
                db.add(flow_rec)
                records_parsed += 1
                offset += record_size

            db.commit()
            logger.debug(f"Parsed {records_parsed} NetFlow v5 records from {exporter_ip}")
        except Exception as e:
            db.rollback()
            logger.error(f"Error parsing NetFlow packets: {e}")
        finally:
            db.close()

    def generate_simulated_flows(self, count: int = 5):
        """Simulates flow traffic in the network for presentation/demo purposes."""
        db = SessionLocalSync()
        try:
            # Common subnets
            local_ips = ["192.168.1.50", "192.168.1.100", "10.0.0.12", "10.0.0.45", "10.2.2.14"]
            remote_ips = ["8.8.8.8", "1.1.1.1", "204.79.197.200", "142.250.190.46"]
            protocols = [6, 17, 1] # TCP, UDP, ICMP
            ports = [80, 443, 22, 53, 3000, 5432]

            for _ in range(count):
                src = random.choice(local_ips)
                dst = random.choice(remote_ips) if random.random() > 0.5 else random.choice(local_ips)
                
                # Symmetrical flip sometimes
                if random.random() > 0.5:
                    src, dst = dst, src

                proto = random.choice(protocols)
                sp = random.randint(1024, 65535) if proto != 1 else 0
                dp = random.choice(ports) if proto != 1 else 0

                octets = random.randint(500, 1000000)
                packets = random.randint(5, 8000)

                flow = FlowRecord(
                    source_ip=src,
                    destination_ip=dst,
                    source_port=sp,
                    destination_port=dp,
                    protocol=proto,
                    octets=octets,
                    packets=packets,
                    start_time=datetime.now() - timedelta(seconds=random.randint(1, 10)),
                    end_time=datetime.now()
                )
                db.add(flow)
            
            db.commit()
            logger.info(f"Generated {count} simulated NetFlow records.")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to generate simulated NetFlows: {e}")
        finally:
            db.close()
