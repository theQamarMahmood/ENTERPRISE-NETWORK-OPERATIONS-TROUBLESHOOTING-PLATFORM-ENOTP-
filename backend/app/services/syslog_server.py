import socket
import re
import threading
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.core.database import SessionLocalSync
from app.models.models import SyslogRecord, Device, Incident
from app.core.config import settings

logger = logging.getLogger("ENOTP_Syslog")

# Standard Cisco Syslog Patterns
# Example: <189>120: *Jun 13 10:14:02.123: %LINK-3-UPDOWN: Interface GigabitEthernet1/0/1, changed state to down
CISCO_SYSLOG_PATTERN = re.compile(
    r"(?:%)(?P<facility>[A-Z0-9_\-]+)-(?P<severity>\d)-(?P<mnemonic>[A-Z0-9_\-]+):\s*(?P<message>.*)"
)

class SyslogServer:
    def __init__(self, host: str = "0.0.0.0", port: int = None):
        self.host = host
        self.port = port or settings.SYSLOG_PORT
        self.socket = None
        self.running = False
        self.thread = None

    def start(self):
        """Starts the Syslog server in a background thread."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind((self.host, self.port))
            self.running = True
            self.thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.thread.start()
            logger.info(f"Syslog server started on {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to start Syslog server on port {self.port}: {e}")

    def stop(self):
        self.running = False
        if self.socket:
            self.socket.close()
        if self.thread:
            self.thread.join(timeout=2.0)
        logger.info("Syslog server stopped.")

    def _listen_loop(self):
        while self.running:
            try:
                data, addr = self.socket.recvfrom(4096)
                ip = addr[0]
                message = data.decode(errors="ignore").strip()
                self._process_syslog(ip, message)
            except Exception as e:
                if self.running:
                    logger.error(f"Error in syslog loop: {e}")

    def _process_syslog(self, client_ip: str, raw_msg: str):
        """Parses the raw syslog string and commits it to PostgreSQL."""
        db: Session = SessionLocalSync()
        try:
            # Clean PRI prefix if present: <189>...
            clean_msg = re.sub(r"^<\d+>", "", raw_msg).strip()
            
            # Match Cisco facility/severity mnemonic patterns
            match = CISCO_SYSLOG_PATTERN.search(clean_msg)
            facility = "GENERIC"
            severity_code = "6"  # informational
            parsed_type = "generic_info"

            if match:
                facility = match.group("facility")
                severity_code = match.group("severity")
                mnemonic = match.group("mnemonic")
                parsed_type = f"{facility.lower()}_{mnemonic.lower()}"
                message_body = match.group("message")
            else:
                message_body = clean_msg

            # Severity mapping: Cisco scale 0-7 -> human readable names
            severity_map = {
                "0": "emergency", "1": "alert", "2": "critical", "3": "error",
                "4": "warning", "5": "notice", "6": "informational", "7": "debug"
            }
            severity_str = severity_map.get(severity_code, "informational")

            # Try to resolve device hostname
            device = db.query(Device).filter(Device.ip_address == client_ip).first()
            hostname = device.hostname if device else client_ip

            # Save to syslogs table
            syslog_rec = SyslogRecord(
                device_ip=client_ip,
                hostname=hostname,
                facility=facility,
                severity=severity_str,
                timestamp=datetime.now(),
                message=message_body,
                parsed_event_type=parsed_type
            )
            db.add(syslog_rec)
            db.flush()

            # Trigger automated correlation / incident generation if severity <= 3 (error/crit/alert)
            if int(severity_code) <= 3:
                self._correlate_incident(db, syslog_rec, device)

            db.commit()
            
            # In a production app, we would push this syslog to redis pubsub/web sockets
            # websockets_manager.broadcast({"event": "NEW_SYSLOG", "data": {...}})
        except Exception as e:
            db.rollback()
            logger.error(f"Failed parsing syslog from {client_ip}: {e}")
        finally:
            db.close()

    def _correlate_incident(self, db: Session, log: SyslogRecord, device: Device):
        """Creates or updates active incidents based on syslog rules."""
        # Check if an open incident already exists for this device & event type to prevent ticket storms
        existing_incident = db.query(Incident).filter(
            Incident.status == "open",
            Incident.root_cause_device_id == (device.id if device else None),
            Incident.root_cause_type == log.parsed_event_type
        ).first()

        if not existing_incident:
            # Create a new incident ticket
            new_incident = Incident(
                title=f"{device.hostname if device else log.device_ip} - {log.facility} Failure",
                description=f"Automated incident created via Syslog alert.\nFacility: {log.facility}\nMessage: {log.message}",
                severity="critical" if log.severity in ["emergency", "alert", "critical"] else "major",
                status="open",
                root_cause_device_id=device.id if device else None,
                root_cause_type=log.parsed_event_type,
                impacted_services={
                    "site": device.site if device else "Unknown",
                    "device_type": device.device_type if device else "Unknown"
                }
            )
            db.add(new_incident)
            db.flush()
            log.correlated_incident_id = new_incident.id
            logger.warning(f"[INCIDENT] Automated ticket opened: {new_incident.title}")
        else:
            # Relate this log to the existing incident
            log.correlated_incident_id = existing_incident.id
            logger.info(f"[INCIDENT] Correlated syslog to ticket {existing_incident.id}")
