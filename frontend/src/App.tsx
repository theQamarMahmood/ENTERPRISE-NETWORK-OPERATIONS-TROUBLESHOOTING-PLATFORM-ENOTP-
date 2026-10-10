import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { 
  Box, Container, Grid, Typography, Card, CardContent, Tabs, Tab, Button, 
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper,
  CircularProgress, Alert, Badge, List, ListItem, ListItemText, Drawer, 
  Divider, TextField, MenuItem, Select, FormControl, InputLabel, Dialog,
  DialogTitle, DialogContent, DialogActions, Chip
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Router as RouterIcon,
  Hub as HubIcon,
  SettingsBackupRestore as BackupIcon,
  Timeline as SimulationIcon,
  ReportProblem as WarningIcon,
  CheckCircle as SuccessIcon,
  Security as SecurityIcon,
  Refresh as RefreshIcon,
  WifiTethering as APIcon,
  VpnKey as TunnelIcon
} from '@mui/icons-material';

// Configure default base URL to redirect to the proxy
axios.defaults.baseURL = 'http://localhost:8000';

function App() {
  const [tabValue, setTabValue] = useState(0);
  const [metrics, setMetrics] = useState<any>(null);
  const [devices, setDevices] = useState<any[]>([]);
  const [selectedDevice, setSelectedDevice] = useState<any>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [newDevicePopup, setNewDevicePopup] = useState<any>(null);
  const [incidents, setIncidents] = useState<any[]>([]);
  
  // Simulation States
  const [simSource, setSimSource] = useState('');
  const [simTarget, setSimTarget] = useState('');
  const [simResult, setSimResult] = useState<any>(null);

  // Config States
  const [configHistory, setConfigHistory] = useState<any[]>([]);
  const [selectedConfigVersion, setSelectedConfigVersion] = useState<any>(null);
  const [configDiff, setConfigDiff] = useState<string>('');

  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState('');

  useEffect(() => {
    fetchDashboardData();
    fetchDevices();
    fetchIncidents();

    // Auto-refresh every 30 seconds
    const interval = setInterval(() => {
      fetchDashboardData();
      fetchDevices();
      fetchIncidents();
    }, 30000);

    // Simulate real-time rogue device arrival after 15 seconds
    const timer = setTimeout(() => {
      setNewDevicePopup({
        hostname: "unauthorized-printer-04",
        ip_address: "192.168.1.185",
        mac_address: "70:f3:5a:1b:22:9e",
        vendor: "Hewlett-Packard",
        vlan: 10,
        switch: "Core-Switch-01",
        port: "Gig1/0/24",
        time: "Just Now"
      });
    }, 15000);
    return () => { clearTimeout(timer); clearInterval(interval); };
  }, []);

  const fetchDashboardData = async () => {
    setLoading(true);
    setApiError('');
    try {
      const res = await axios.get('/api/v1/dashboard/metrics');
      setMetrics(res.data);
      setApiError('');
    } catch (err: any) {
      console.error("Failed to fetch dashboard metrics", err);
      setApiError('Cannot connect to ENOTP backend at http://localhost:8000. Make sure the backend server is running.');
    } finally {
      setLoading(false);
    }
  };

  const fetchDevices = async () => {
    try {
      const res = await axios.get('/api/v1/devices');
      setDevices(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchIncidents = async () => {
    try {
      const res = await axios.get('/api/v1/incidents');
      setIncidents(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeviceClick = async (device: any) => {
    try {
      const res = await axios.get(`/api/v1/devices/${device.id}`);
      setSelectedDevice(res.data);
      setDrawerOpen(true);
      
      // Load config history
      const configRes = await axios.get(`/api/v1/devices/${device.id}/configs`);
      setConfigHistory(configRes.data);
      setConfigDiff('');
      setSelectedConfigVersion(null);
    } catch (err) {
      console.error(err);
    }
  };

  const triggerConfigBackup = async (deviceId: string) => {
    try {
      await axios.post(`/api/v1/devices/${deviceId}/backup`);
      const configRes = await axios.get(`/api/v1/devices/${deviceId}/configs`);
      setConfigHistory(configRes.data);
      alert("Configuration backup captured successfully!");
    } catch (err) {
      alert("Backup failed: Check SSH config.");
    }
  };

  const handleCompareConfigs = async (verA: number, verB: number) => {
    if (!selectedDevice) return;
    try {
      const res = await axios.get(`/api/v1/devices/${selectedDevice.id}/configs/compare/${verA}/${verB}`);
      setConfigDiff(res.data.diff);
    } catch (err) {
      alert("Failed to compare configs.");
    }
  };

  const runShutdownSimulation = async () => {
    if (!simSource || !simTarget) return;
    try {
      const res = await axios.post(`/api/v1/twin/simulate-link-shutdown?source=${simSource}&target=${simTarget}`);
      setSimResult(res.data);
    } catch (err) {
      alert("Simulation failed. Verify device names.");
    }
  };

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default', pb: 8 }}>
      {/* Header bar */}
      <Box sx={{ borderBottom: 1, borderColor: 'rgba(255, 255, 255, 0.08)', py: 2, px: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(15, 22, 42, 0.4)', backdropFilter: 'blur(8px)' }}>
        <Typography variant="h5" sx={{ fontWeight: 800, fontFamily: 'Outfit', color: 'primary.main', display: 'flex', alignItems: 'center', gap: 1 }}>
          <SecurityIcon /> ENOTP
          <Typography component="span" sx={{ color: 'text.secondary', fontSize: 16, fontWeight: 400 }}>
            | Enterprise Network Operations
          </Typography>
        </Typography>
        <Button variant="outlined" startIcon={<RefreshIcon />} size="small" onClick={() => { fetchDashboardData(); fetchDevices(); fetchIncidents(); }}>
          Sync Platform
        </Button>
      </Box>

      {/* Main Tabs Container */}
      <Container maxWidth="xl" sx={{ mt: 4 }}>
        <Tabs value={tabValue} onChange={(e, val) => setTabValue(val)} sx={{ mb: 4, borderBottom: 1, borderColor: 'rgba(255, 255, 255, 0.08)' }} textColor="primary" indicatorColor="primary">
          <Tab icon={<DashboardIcon />} iconPosition="start" label="NOC Dashboard" />
          <Tab icon={<RouterIcon />} iconPosition="start" label="Device Inventory" />
          <Tab icon={<HubIcon />} iconPosition="start" label="Topology Mapping" />
          <Tab icon={<SimulationIcon />} iconPosition="start" label="Digital Twin Simulator" />
        </Tabs>

        {/* TAB 0: DASHBOARD */}
        {tabValue === 0 && (
          <Box>
            {loading && !metrics && (
              <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300, flexDirection: 'column', gap: 2 }}>
                <CircularProgress size={60} />
                <Typography color="text.secondary">Connecting to ENOTP Backend...</Typography>
              </Box>
            )}
            {apiError && (
              <Alert severity="error" sx={{ mb: 3 }} action={
                <Button color="inherit" size="small" onClick={fetchDashboardData}>Retry</Button>
              }>
                {apiError}
              </Alert>
            )}
            {metrics && (
              <Grid container spacing={3}>
            {/* Health indicators */}
            <Grid item xs={12}>
              <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>Real-Time System Health Scores</Typography>
              <Grid container spacing={2}>
                {[
                  { name: 'Core Infrastructure', score: metrics.network_health_score, color: 'success.main' },
                  { name: 'Routing Protocols', score: metrics.routing_health, color: 'primary.main' },
                  { name: 'Switching / Spanning Tree', score: metrics.switching_health, color: 'info.main' },
                  { name: 'IPSec & Tunnels', score: metrics.vpn_health, color: 'secondary.main' }
                ].map((item, idx) => (
                  <Grid item xs={6} md={3} key={idx}>
                    <Card sx={{ p: 2, textAlign: 'center' }}>
                      <Box sx={{ position: 'relative', display: 'inline-flex' }}>
                        <CircularProgress variant="determinate" value={item.score} size={80} thickness={5} sx={{ color: item.color }} />
                        <Box sx={{ top: 0, left: 0, bottom: 0, right: 0, position: 'absolute', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <Typography variant="h6" component="div" color="text.primary">{item.score}%</Typography>
                        </Box>
                      </Box>
                      <Typography variant="subtitle2" sx={{ mt: 1, color: 'text.secondary' }}>{item.name}</Typography>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            </Grid>

            {/* Metrics cards */}
            <Grid item xs={12} md={8}>
              <Grid container spacing={2}>
                <Grid item xs={6} sm={3}>
                  <Card><CardContent><Typography color="text.secondary">Total Devices</Typography><Typography variant="h4">{metrics.total_devices}</Typography></CardContent></Card>
                </Grid>
                <Grid item xs={6} sm={3}>
                  <Card><CardContent><Typography color="success.main">Online Devices</Typography><Typography variant="h4">{metrics.online_devices}</Typography></CardContent></Card>
                </Grid>
                <Grid item xs={6} sm={3}>
                  <Card><CardContent><Typography color="error.main">Offline Devices</Typography><Typography variant="h4">{metrics.offline_devices}</Typography></CardContent></Card>
                </Grid>
                <Grid item xs={6} sm={3}>
                  <Card><CardContent><Typography color="warning.main">Open Incidents</Typography><Typography variant="h4">{metrics.active_incidents}</Typography></CardContent></Card>
                </Grid>
              </Grid>

              {/* Incidents / Alerts List */}
              <Card sx={{ mt: 3 }}>
                <CardContent>
                  <Typography variant="h6" sx={{ mb: 2 }}>Correlated Incident Log</Typography>
                  <List>
                    {incidents.length === 0 ? (
                      <Alert severity="success">All devices reporting normal operations. Zero active outages.</Alert>
                    ) : (
                      incidents.map((inc) => (
                        <ListItem key={inc.id} sx={{ mb: 1, bgcolor: 'rgba(244, 63, 94, 0.05)', border: '1px solid rgba(244, 63, 94, 0.15)', borderRadius: 2 }}>
                          <WarningIcon color="error" sx={{ mr: 2 }} />
                          <ListItemText primary={inc.title} secondary={inc.description} />
                          <Chip label={inc.severity.toUpperCase()} color={inc.severity === 'critical' ? 'error' : 'warning'} size="small" />
                        </ListItem>
                      ))
                    )}
                  </List>
                </CardContent>
              </Card>
            </Grid>

            {/* Traffic & Top Bandwidth side panel */}
            <Grid item xs={12} md={4}>
              <Card>
                <CardContent>
                  <Typography variant="h6" sx={{ mb: 2 }}>NetFlow Analytics (Top Bandwidth)</Typography>
                  <TableContainer component={Paper} sx={{ bgcolor: 'transparent', boxShadow: 'none' }}>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>IP Address</TableCell>
                          <TableCell>Protocol</TableCell>
                          <TableCell align="right">Mbps</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {metrics.top_bandwidth_consumers.map((item: any, idx: number) => (
                          <TableRow key={idx}>
                            <TableCell>{item.ip}</TableCell>
                            <TableCell>{item.protocol}</TableCell>
                            <TableCell align="right" sx={{ color: 'primary.main', fontWeight: 600 }}>{item.bandwidth_mbps}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            </Grid>
              </Grid>
            )}
          </Box>
        )}


        {/* TAB 1: DEVICES */}
        {tabValue === 1 && (
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Typography variant="h6" sx={{ mb: 2 }}>Monitored Network Infrastructure</Typography>
              <TableContainer component={Card}>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Hostname</TableCell>
                      <TableCell>IP Address</TableCell>
                      <TableCell>Vendor / Model</TableCell>
                      <TableCell>Site Location</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell align="right">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {devices.map((dev) => (
                      <TableRow key={dev.id} hover style={{ cursor: 'pointer' }} onClick={() => handleDeviceClick(dev)}>
                        <TableCell sx={{ fontWeight: 600 }}>{dev.hostname}</TableCell>
                        <TableCell>{dev.ip_address}</TableCell>
                        <TableCell>{dev.vendor} {dev.model}</TableCell>
                        <TableCell>{dev.site}</TableCell>
                        <TableCell>
                          <Chip label={dev.status.toUpperCase()} color={dev.status === 'online' ? 'success' : 'error'} size="small" />
                        </TableCell>
                        <TableCell align="right" onClick={(e) => e.stopPropagation()}>
                          <Button variant="outlined" size="small" onClick={() => triggerConfigBackup(dev.id)}>Backup Config</Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Grid>
          </Grid>
        )}

        {/* TAB 2: TOPOLOGY */}
        {tabValue === 2 && (
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>Interactive Network Topology Map</Typography>
              {/* Topology SVG Layout Representation */}
              <Box sx={{ border: '1px solid rgba(255,255,255,0.08)', borderRadius: 4, height: 500, bgcolor: '#0b0f19', display: 'flex', position: 'relative', overflow: 'hidden' }}>
                {/* SVG Visualizer */}
                <svg style={{ width: '100%', height: '100%' }}>
                  {/* Dynamic links */}
                  <line x1="150" y1="250" x2="400" y2="150" stroke="rgba(255,255,255,0.15)" strokeWidth="3" />
                  <line x1="150" y1="250" x2="400" y2="350" stroke="rgba(255,255,255,0.15)" strokeWidth="3" />
                  <line x1="400" y1="150" x2="700" y2="250" stroke="#00f2fe" strokeWidth="4" />
                  <line x1="400" y1="350" x2="700" y2="250" stroke="#f43f5e" strokeWidth="4" strokeDasharray="5" />
                  
                  {/* Nodes */}
                  <circle cx="150" cy="250" r="30" fill="#00f2fe" />
                  <text x="150" y="300" textAnchor="middle" fill="#94a3b8" fontSize="12">FW-Edge-01</text>
                  
                  <circle cx="400" cy="150" r="30" fill="#10b981" />
                  <text x="400" y="200" textAnchor="middle" fill="#94a3b8" fontSize="12">Dist-Switch-01</text>

                  <circle cx="400" cy="350" r="30" fill="#f43f5e" />
                  <text x="400" y="400" textAnchor="middle" fill="#94a3b8" fontSize="12">Dist-Switch-02 (RCA Down)</text>

                  <circle cx="700" cy="250" r="35" fill="#9d4edd" />
                  <text x="700" y="305" textAnchor="middle" fill="#94a3b8" fontSize="12">Core-Switch-01</text>
                </svg>
                <Box sx={{ position: 'absolute', top: 16, right: 16, p: 2, border: '1px solid rgba(255,255,255,0.08)', borderRadius: 2, bgcolor: 'rgba(15,22,42,0.85)' }}>
                  <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>Legend</Typography>
                  <Typography variant="caption" display="block" sx={{ color: 'success.main' }}>● Switch (Healthy)</Typography>
                  <Typography variant="caption" display="block" sx={{ color: 'error.main' }}>● Switch (Faulted / Down)</Typography>
                  <Typography variant="caption" display="block" sx={{ color: 'primary.main' }}>● Active Backbone Link</Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        )}

        {/* TAB 3: DIGITAL TWIN */}
        {tabValue === 3 && (
          <Grid container spacing={3}>
            <Grid item xs={12} md={4}>
              <Card>
                <CardContent>
                  <Typography variant="h6" sx={{ mb: 2 }}>Simulate Failures & Traffic Re-routing</Typography>
                  <TextField fullWidth label="Source Device Hostname" value={simSource} onChange={(e) => setSimSource(e.target.value)} placeholder="e.g. Core-Switch-01" sx={{ mb: 2 }} />
                  <TextField fullWidth label="Target Device Hostname" value={simTarget} onChange={(e) => setSimTarget(e.target.value)} placeholder="e.g. Dist-Switch-02" sx={{ mb: 3 }} />
                  <Button fullWidth variant="contained" color="secondary" onClick={runShutdownSimulation}>Run Simulation</Button>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={8}>
              <Card sx={{ minHeight: 250 }}>
                <CardContent>
                  <Typography variant="h6" sx={{ mb: 2 }}>Simulation Prediction Results</Typography>
                  {simResult ? (
                    <Box>
                      <Alert severity={simResult.risk_level === 'critical' ? 'error' : 'warning'} sx={{ mb: 2 }}>
                        {simResult.summary}
                      </Alert>
                      <Typography variant="subtitle2" sx={{ mt: 2, fontWeight: 600 }}>Isolated Devices:</Typography>
                      {simResult.isolated_devices.length === 0 ? (
                        <Typography variant="body2" color="text.secondary">None (Redundancy preserved)</Typography>
                      ) : (
                        simResult.isolated_devices.map((d: any, idx: number) => <Chip key={idx} label={d} color="error" sx={{ m: 0.5 }} />)
                      )}
                      <Typography variant="subtitle2" sx={{ mt: 2, fontWeight: 600 }}>Impacted Sites:</Typography>
                      {simResult.isolated_sites.length === 0 ? (
                        <Typography variant="body2" color="text.secondary">None</Typography>
                      ) : (
                        simResult.isolated_sites.map((s: any, idx: number) => <Chip key={idx} label={s} color="warning" sx={{ m: 0.5 }} />)
                      )}
                    </Box>
                  ) : (
                    <Typography color="text.secondary">Input source/target nodes and click Run Simulation to forecast routing shifts and device isolation risks.</Typography>
                  )}
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        )}
      </Container>

      {/* DEVICE DETAILS DRAWER (KNOWLEDGE CENTER) */}
      <Drawer anchor="right" open={drawerOpen} onClose={() => setDrawerOpen(false)} PaperProps={{ sx: { width: 600, borderLeft: '1px solid rgba(255,255,255,0.08)', bgcolor: '#0b0f19' } }}>
        {selectedDevice && (
          <Box sx={{ p: 4 }}>
            <Typography variant="h5" sx={{ mb: 1, fontWeight: 700 }}>{selectedDevice.hostname}</Typography>
            <Typography color="text.secondary" sx={{ mb: 3 }}>IP: {selectedDevice.ip_address} | Vendor: {selectedDevice.vendor} ({selectedDevice.model})</Typography>
            <Divider sx={{ my: 2, borderColor: 'rgba(255,255,255,0.08)' }} />
            
            {/* Interfaces status */}
            <Typography variant="h6" sx={{ mb: 1 }}>Port Interfaces</Typography>
            <TableContainer component={Paper} sx={{ bgcolor: 'transparent', boxShadow: 'none' }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Port</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell align="right">Bandwidth</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {selectedDevice.interfaces && selectedDevice.interfaces.map((iface: any) => (
                    <TableRow key={iface.id}>
                      <TableCell>{iface.name}</TableCell>
                      <TableCell><Chip label={iface.status.toUpperCase()} size="small" color={iface.status === 'up' ? 'success' : 'error'} /></TableCell>
                      <TableCell align="right">{iface.speed} Mbps</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>

            {/* Config backups */}
            <Typography variant="h6" sx={{ mt: 4, mb: 1 }}>Configuration Management</Typography>
            <List>
              {configHistory.map((backup) => (
                <ListItem key={backup.id} secondaryAction={
                  <Button size="small" variant="outlined" onClick={() => handleCompareConfigs(backup.version - 1 || 1, backup.version)}>Compare Diff</Button>
                }>
                  <ListItemText primary={`Version ${backup.version}`} secondary={new Date(backup.created_at).toLocaleString()} />
                </ListItem>
              ))}
            </List>

            {configDiff && (
              <Box sx={{ mt: 2, p: 2, bgcolor: '#020617', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 2, maxHeight: 200, overflowY: 'auto' }}>
                <Typography variant="caption" component="pre" style={{ margin: 0, color: '#f43f5e', fontFamily: 'monospace' }}>
                  {configDiff}
                </Typography>
              </Box>
            )}
          </Box>
        )}
      </Drawer>

      {/* NEW DEVICE DETECTED POPUP */}
      <Dialog open={!!newDevicePopup} onClose={() => setNewDevicePopup(null)}>
        {newDevicePopup && (
          <Box sx={{ p: 2 }}>
            <DialogTitle sx={{ color: 'warning.main', display: 'flex', alignItems: 'center', gap: 1 }}>
              <WarningIcon /> New Unapproved Device Detected
            </DialogTitle>
            <DialogContent>
              <Typography variant="body2" sx={{ mb: 2 }}>A new host has connected to an enterprise access switch port. Please authorize or quarantine immediately.</Typography>
              <Table size="small">
                <TableBody>
                  <TableRow><TableCell>Hostname</TableCell><TableCell>{newDevicePopup.hostname}</TableCell></TableRow>
                  <TableRow><TableCell>IP Address</TableCell><TableCell>{newDevicePopup.ip_address}</TableCell></TableRow>
                  <TableRow><TableCell>MAC Address</TableCell><TableCell>{newDevicePopup.mac_address}</TableCell></TableRow>
                  <TableRow><TableCell>Location</TableCell><TableCell>{newDevicePopup.switch} - Port {newDevicePopup.port}</TableCell></TableRow>
                </TableBody>
              </Table>
            </DialogContent>
            <DialogActions>
              <Button color="success" variant="contained" onClick={() => setNewDevicePopup(null)}>Approve & Trust</Button>
              <Button color="error" variant="outlined" onClick={() => setNewDevicePopup(null)}>Quarantine / Block</Button>
              <Button color="inherit" onClick={() => setNewDevicePopup(null)}>Ignore</Button>
            </DialogActions>
          </Box>
        )}
      </Dialog>
    </Box>
  );
}

export default App;
