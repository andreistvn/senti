import React, { useState, useEffect, useRef, useLayoutEffect } from 'react';
import {
  Shield, Radio, Clock, Activity, Database,
  TrendingUp, Users, RefreshCw, Cpu, Server, Award, LogOut
} from 'lucide-react';
import { LineChart, Line, ResponsiveContainer } from 'recharts';
import { Power } from 'lucide-react';
import { useTrayConnection } from '../hooks/useTrayConnection';

type Tab = 'dashboard' | 'diagnostics';

interface DaemonService {
  id: string;
  name: string;
  status: 'active' | 'loaded' | 'connected' | 'degraded' | 'offline';
  detail: string;
  uptime: string;
}

const INITIAL_DAEMONS: DaemonService[] = [
  { id: 'scapy',  name: 'Scapy Sniffer',     status: 'active',    detail: 'Capturing ARP frames on wlan0',          uptime: '4h 23m' },
  { id: 'ml',     name: 'Tier-2 ML Engine',   status: 'loaded',    detail: 'RandomForest model v3.1 in memory',      uptime: '4h 23m' },
  { id: 'ws',     name: 'WebSocket Relay',    status: 'connected', detail: 'relay.dict.gov.ph:8443 · 12ms ping',     uptime: '4h 21m' },
  { id: 'arp',    name: 'ARP Guard Module',   status: 'active',    detail: 'Monitoring 34 active hosts',             uptime: '4h 23m' },
  { id: 'bayanihan', name: 'Bayanihan Agent', status: 'connected', detail: 'Peer mesh: 40 nodes reachable',          uptime: '4h 18m' },
];

export default function Dashboard({ onLogout }: { onLogout: () => void }) {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');

  /* live telemetry */
  const [cpuData, setCpuData] = useState(
    Array.from({ length: 60 }, (_, i) => ({ time: i, usage: Math.random() * 15 + 2 }))
  );
  const [memoryUsage, setMemoryUsage] = useState(84);
  const [lastUpdate, setLastUpdate] = useState(3);
  const [inspected, setInspected] = useState(1247);
  const [dropped, setDropped] = useState(23);
  const [passed, setPassed] = useState(1224);

  /* Bayanihan */
  const [sigContributions, setSigContributions] = useState(15);
  const [usersProtected, setUsersProtected] = useState(40);

  /* daemons */
  const [daemons, setDaemons] = useState<DaemonService[]>(INITIAL_DAEMONS);
  const [restarting, setRestarting] = useState<string | null>(null);

  /* live connection to the local Python tray daemon (tray-app/) */
  const tray = useTrayConnection();
  const live = tray.connected;
  const liveCpu = tray.stats?.cpu;

  useEffect(() => {
    const interval = setInterval(() => {
      if (live) {
        setCpuData(prev => [
          ...prev.slice(1),
          { time: prev[prev.length - 1].time + 1, usage: liveCpu ?? prev[prev.length - 1].usage }
        ]);
        return;
      }
      setCpuData(prev => [
        ...prev.slice(1),
        { time: prev[prev.length - 1].time + 1, usage: Math.random() * 15 + 2 }
      ]);
      setMemoryUsage(Math.floor(Math.random() * 30 + 70));
      setLastUpdate(Math.floor(Math.random() * 10) + 1);
      setInspected(p => p + Math.floor(Math.random() * 10 + 2));
      setDropped(p => Math.random() > 0.7 ? p + 1 : p);
      setPassed(p => p + Math.floor(Math.random() * 9 + 2));
      if (Math.random() > 0.92) {
        setSigContributions(c => c + 1);
        setUsersProtected(u => u + Math.floor(Math.random() * 3));
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [live, liveCpu]);

  const eProtected     = live ? (tray.status?.protected ?? false) : true;
  const eInspected     = live ? (tray.stats?.inspected ?? 0) : inspected;
  const eDropped       = live ? (tray.stats?.dropped ?? 0) : dropped;
  const ePassed        = live ? (tray.stats?.passed ?? 0) : passed;
  const eMemory        = live ? (tray.stats?.memory ?? 0) : memoryUsage;
  const eSigContrib    = live ? (tray.stats?.bayanihan.contributions ?? 0) : sigContributions;
  const eUsersProtected= live ? (tray.stats?.bayanihan.usersProtected ?? 0) : usersProtected;
  const eLastThreat    = live
    ? tray.stats?.lastThreat ?? null
    : { attackType: 'ARP Spoofing', sourceMac: 'A4:5E:60:E2:3B:1C', timestamp: '2 minutes ago' };
  const eDaemons       = live && tray.services ? (tray.services as DaemonService[]) : daemons;

  /* detection logs */
  const detectionLogs = [
    { id: 1, timestamp: '2026-06-10 14:32:18', sourceMac: 'A4:5E:60:E2:3B:1C', attackType: 'ARP Spoofing',  tier: 'Tier 1', action: 'Blocked' },
    { id: 2, timestamp: '2026-06-10 14:31:45', sourceMac: 'B8:27:EB:4F:92:D3', attackType: 'ARP Spoofing',  tier: 'Tier 2', action: 'Dropped' },
    { id: 3, timestamp: '2026-06-10 14:29:12', sourceMac: '00:1A:7D:DA:71:13', attackType: 'ARP Spoofing',  tier: 'Tier 1', action: 'Blocked' },
    { id: 4, timestamp: '2026-06-10 14:27:08', sourceMac: 'DC:A6:32:1F:E8:9A', attackType: 'ARP Spoofing',  tier: 'Tier 1', action: 'Blocked' },
    { id: 5, timestamp: '2026-06-10 14:25:33', sourceMac: '2C:F0:5D:8B:42:A7', attackType: 'ARP Spoofing',  tier: 'Tier 2', action: 'Dropped' },
    { id: 6, timestamp: '2026-06-10 14:23:51', sourceMac: 'F4:5C:89:C3:2D:6E', attackType: 'ARP Spoofing',  tier: 'Tier 1', action: 'Blocked' },
  ];
  const eLogs = live && tray.events && tray.events.length ? tray.events : detectionLogs;

  const detectionLogsContainerRef = useRef<HTMLDivElement>(null);
  const prevDetectionLogsSnapshotRef = useRef<{ length: number; scrollTop: number; scrollHeight: number; clientHeight: number } | null>(null);

  useLayoutEffect(() => {
    const c = detectionLogsContainerRef.current;
    const prev = prevDetectionLogsSnapshotRef.current;
    if (!c) { prevDetectionLogsSnapshotRef.current = null; return; }

    if (!prev) {
      prevDetectionLogsSnapshotRef.current = { length: eLogs.length, scrollTop: c.scrollTop, scrollHeight: c.scrollHeight, clientHeight: c.clientHeight };
      return;
    }

    prevDetectionLogsSnapshotRef.current = { length: eLogs.length, scrollTop: c.scrollTop, scrollHeight: c.scrollHeight, clientHeight: c.clientHeight };
  }, [eLogs]);

  /* daemon restart */
  function restartDaemon(id: string) {
    setRestarting(id);
    setDaemons(prev => prev.map(d => d.id === id ? { ...d, status: 'degraded' as const, detail: 'Restarting…', uptime: '0s' } : d));
    setTimeout(() => {
      setDaemons(prev => prev.map(d => {
        if (d.id !== id) return d;
        const orig = INITIAL_DAEMONS.find(x => x.id === id)!;
        return { ...orig, uptime: '0m 4s' };
      }));
      setRestarting(null);
    }, 2200);
  }

  const statusColor = (s: DaemonService['status']) =>
    s === 'active' || s === 'loaded' || s === 'connected' ? '#00aa55' :
    s === 'degraded' ? '#f59e0b' : '#c0392b';

  const statusLabel = (s: DaemonService['status']) =>
    ({ active: 'ACTIVE', loaded: 'LOADED', connected: 'CONNECTED', degraded: 'DEGRADED', offline: 'OFFLINE' }[s]);

  /* ── tabs config ── */
  const TABS: { id: Tab; label: string; Icon: any }[] = [
    { id: 'dashboard',   label: 'DASHBOARD',   Icon: Activity },
    { id: 'diagnostics', label: 'DIAGNOSTICS', Icon: Cpu },
  ];

  return (
    <div className="min-h-screen bg-[#e8eaed] flex flex-col">

      {/* Header */}
      <header className="bg-[#0d1b3e] border-b-2 border-[#c0392b] px-6 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <Shield className="w-5 h-5 text-white" strokeWidth={2} />
          <span className="text-white tracking-widest text-sm font-bold uppercase">SentiNet Agent Dashboard</span>
        </div>
        <div className="flex items-center gap-6 text-xs">
          <span className="text-[#8899bb] tracking-wider">192.168.1.42 / A4:5E:60:E2:3B:1C</span>
          {live ? (
            <span className="flex items-center gap-2 text-[#00ff88]">
              <span className="w-2 h-2 rounded-full bg-[#00ff88] animate-pulse inline-block" />
              TRAY CONNECTED
            </span>
          ) : (
            <span className="flex items-center gap-2 text-[#f59e0b]" title="Tray daemon not detected — showing simulated data">
              <span className="w-2 h-2 rounded-full bg-[#f59e0b] animate-pulse inline-block" />
              MOCK MODE
            </span>
          )}
        </div>
      </header>

      {/* Tab Bar */}
      <div className="bg-white border-b border-[#cccccc] flex items-center justify-between shrink-0">
        <div className="flex">
          {TABS.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-2 px-5 py-3 text-[10px] tracking-widest uppercase border-r border-[#cccccc] transition ${
                activeTab === id ? 'bg-[#0d1b3e] text-white' : 'bg-white text-[#555] hover:bg-[#f0f0f0]'
              }`}
            >
              <Icon className="w-3.5 h-3.5" /> {label}
            </button>
          ))}
        </div>

        <div className="flex">
          <button 
            onClick={onLogout} 
            className="flex items-center gap-2 px-6 py-3 text-[10px] tracking-widest text-[#c0392b] hover:bg-red-50 border-l border-[#cccccc] uppercase transition"
          >
            <LogOut className="w-4 h-4" /> Logout
          </button>
        </div>
      </div>

      {/* ── DASHBOARD tab ── */}
      {activeTab === 'dashboard' && (
        <div className="flex-1 p-5 space-y-4 overflow-auto max-w-[1800px] mx-auto w-full">

          {/* Row 1: Status Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white border border-[#cccccc]">
              <PanelHeader icon={<Shield className="w-4 h-4 text-[#0d1b3e]" strokeWidth={2} />} title="Protection Status" />
              <div className="p-5">
                <div
                  className="inline-flex items-center gap-2 px-5 py-2.5 mb-3"
                  style={{ background: eProtected ? '#00aa55' : '#3a5070' }}
                >
                  <ShieldCheckIcon />
                  <span className="text-white text-sm tracking-[0.2em] font-bold">
                    {eProtected ? 'PROTECTED' : 'UNPROTECTED'}
                  </span>
                </div>
                <p className="text-[#888] text-[10px] tracking-wider mb-3">
                  {eProtected ? 'All local threats actively blocked' : 'Protection is currently disabled'}
                </p>
                {live && (
                  <button
                    onClick={() => tray.toggle()}
                    className={`flex items-center gap-2 text-[10px] tracking-widest uppercase px-3 py-1.5 border transition ${
                      eProtected
                        ? 'border-[#c0392b] text-[#c0392b] hover:bg-red-50'
                        : 'border-[#00aa55] text-[#00aa55] hover:bg-green-50'
                    }`}
                  >
                    <Power className="w-3 h-3" />
                    {eProtected ? 'TURN OFF PROTECTION' : 'TURN ON PROTECTION'}
                  </button>
                )}
              </div>
            </div>

            <div className="bg-white border border-[#cccccc]">
              <PanelHeader icon={<Radio className="w-4 h-4 text-[#0d1b3e]" strokeWidth={2} />} title="Relay Connection" />
              <div className="p-5">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-2.5 h-2.5 shrink-0" style={{ background: eProtected ? '#00aa55' : '#3a5070' }} />
                  <span className="text-[#111] text-sm tracking-widest font-bold">
                    RELAY: {eProtected ? 'ONLINE' : 'OFFLINE'}
                  </span>
                </div>
                <p className="text-[#888] text-[10px] tracking-wider">
                  {eProtected ? 'Connected to DICT Central Relay' : 'Relay link down — protection off'}
                </p>
              </div>
            </div>

            <div className="bg-white border border-[#cccccc]">
              <PanelHeader icon={<Clock className="w-4 h-4 text-[#c0392b]" strokeWidth={2} />} title="Last Detected Threat" />
              <div className="p-5">
                <p className="text-[#111] text-sm tracking-widest font-bold mb-3">
                  {eLastThreat ? eLastThreat.timestamp : 'NONE DETECTED'}
                </p>
                <p className="text-[#888] text-[10px] tracking-wider">
                  {eLastThreat ? `${eLastThreat.attackType} from ${eLastThreat.sourceMac}` : 'No threats blocked yet'}
                </p>
              </div>
            </div>
          </div>

          {/* Row 2: Telemetry */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white border border-[#cccccc]">
              <PanelHeader icon={<Activity className="w-4 h-4 text-[#1a4fd6]" strokeWidth={2} />} title="CPU Load (Tier-1 Efficiency)" />
              <div className="p-5">
                <ResponsiveContainer width="100%" height={80}>
                  <LineChart data={cpuData}>
                    <Line type="monotone" dataKey="usage" stroke="#1a4fd6" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
                <div className="flex items-baseline gap-2 mt-2">
                  <span className="text-[#111] text-xl font-bold tracking-widest">{cpuData[cpuData.length - 1].usage.toFixed(1)}%</span>
                  <span className="text-[#00aa55] text-[10px] tracking-widest">LOW IMPACT</span>
                </div>
              </div>
            </div>

            <div className="bg-white border border-[#cccccc]">
              <PanelHeader icon={<Database className="w-4 h-4 text-[#1a4fd6]" strokeWidth={2} />} title="Memory Usage" />
              <div className="p-5 flex flex-col items-center">
                <div className="relative w-28 h-28">
                  <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                    <circle cx="50" cy="50" r="42" stroke="#e0e0e0" strokeWidth="10" fill="none" />
                    <circle cx="50" cy="50" r="42" stroke="#1a4fd6" strokeWidth="10" fill="none"
                      strokeDasharray={`${2 * Math.PI * 42}`}
                      strokeDashoffset={`${2 * Math.PI * 42 * (1 - eMemory / 256)}`}
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-[#111] text-base font-bold">{eMemory} MB</span>
                  </div>
                </div>
                <p className="text-[#888] text-[10px] tracking-wider mt-2">Out of 256 MB allocated</p>
              </div>
            </div>

            <div className="bg-white border border-[#cccccc]">
              <PanelHeader icon={<TrendingUp className="w-4 h-4 text-[#1a4fd6]" strokeWidth={2} />} title="Traffic Throughput (PPS)" />
              <div className="p-5 space-y-3">
                {[
                  { label: 'INSPECTED', value: eInspected.toLocaleString(), pct: 82, color: '#1a4fd6', textColor: '#111', hideBar: true },
                  { label: 'DROPPED',   value: eDropped.toLocaleString(),   pct: Math.min(eInspected ? eDropped / eInspected * 100 : 0, 30), color: '#c0392b', textColor: '#c0392b' },
                  { label: 'PASSED',    value: ePassed.toLocaleString(),    pct: 90, color: '#00aa55', textColor: '#00aa55' },
                ].map(item => (
                  <div key={item.label}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[#555] text-[10px] tracking-widest">{item.label}</span>
                      <span className="text-sm font-bold tracking-widest" style={{ color: item.textColor }}>{item.value}</span>
                    </div>
                    {!item.hideBar && (
                      <div className="w-full bg-[#e0e0e0] h-2">
                        <div className="h-2 transition-all duration-700" style={{ width: `${item.pct}%`, background: item.color }} />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Row 3: Detection Log + Sidebar */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2 bg-white border border-[#cccccc] flex flex-col">
              <div className="px-4 py-3 border-b border-[#cccccc] bg-[#f5f5f5]">
                <p className="text-[#0d1b3e] text-[10px] tracking-widest uppercase font-bold">Detection Log</p>
                <p className="text-[#888] text-[9px] tracking-wider mt-0.5">Real-time threat detection activity</p>
              </div>
              <div className="flex-1 overflow-x-auto">
                <div ref={detectionLogsContainerRef} className="h-full max-h-[36rem] overflow-y-auto">
                  <table className="w-full text-xs min-w-full">
                  <thead>
                    <tr className="border-b border-[#e0e0e0] bg-[#fafafa]">
                      {['TIMESTAMP', 'SOURCE MAC', 'ATTACK TYPE', 'TIER', 'ACTION'].map(h => (
                        <th key={h} className="px-4 py-2.5 text-left text-[#555] tracking-widest font-normal text-[10px]">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {eLogs.map(log => (
                      <tr key={log.id} className="border-b border-[#f0f0f0] bg-[#fff5f5] hover:bg-[#ffe8e8] transition-colors">
                        <td className="px-4 py-3 text-[#555] text-[10px] font-mono">{log.timestamp}</td>
                        <td className="px-4 py-3 text-[#111] text-[10px] tracking-wider font-mono">{log.sourceMac}</td>
                        <td className="px-4 py-3 text-[#c0392b] font-bold text-[10px] tracking-wider">{log.attackType}</td>
                        <td className="px-4 py-3">
                          <span className="bg-[#0d1b3e] text-white text-[9px] tracking-widest px-2 py-0.5">{log.tier}</span>
                        </td>
                        <td className="px-4 py-3">
                          <span className="border border-[#c0392b] text-[#c0392b] text-[9px] tracking-widest px-2 py-0.5">{log.action}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  </table>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              {/* Bayanihan Tracker */}
              <div className="bg-white border border-[#cccccc]">
                <div className="flex items-center gap-2 px-4 py-3 border-b border-[#cccccc] bg-[#0d1b3e]">
                  <Award className="w-3.5 h-3.5 text-[#f59e0b]" strokeWidth={2} />
                  <span className="text-white text-[10px] tracking-widest uppercase font-bold">Bayanihan Contribution</span>
                </div>
                <div className="p-4">
                  <div className="flex items-baseline gap-2 mb-1">
                    <span className="text-[#111] text-3xl font-bold tracking-widest">{eSigContrib}</span>
                    <span className="text-[#888] text-[10px] tracking-wider">signatures</span>
                  </div>
                  <p className="text-[#555] text-[10px] tracking-wider mb-3">
                    Your node submitted <span className="text-[#0d1b3e] font-bold">{eSigContrib} threat signatures</span> to the blockchain today.
                  </p>
                  <div className="bg-[#f0f7ff] border border-[#1a4fd6]/30 px-3 py-2">
                    <div className="flex items-center gap-2">
                      <Users className="w-3 h-3 text-[#1a4fd6]" />
                      <span className="text-[#1a4fd6] text-[10px] tracking-wider font-bold">Protecting {eUsersProtected} other users today</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* WebSocket Pulse */}
              <div className="bg-white border border-[#cccccc]">
                <PanelHeader icon={<Activity className="w-3.5 h-3.5 text-[#0d1b3e]" strokeWidth={2} />} title="WebSocket Pulse" />
                <div className="p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <div className="w-2 h-2 bg-[#00aa55] animate-pulse" />
                    <span className="text-[#111] text-xs tracking-widest font-bold">ACTIVE</span>
                  </div>
                  <p className="text-[#888] text-[10px] tracking-wider">Last update: {lastUpdate}s ago</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── DIAGNOSTICS tab ── */}
      {activeTab === 'diagnostics' && (
        <div className="flex-1 p-5 space-y-5 overflow-auto max-w-[1800px] mx-auto w-full">
          <div>
            <h2 className="text-[#0d1b3e] text-sm tracking-widest font-bold uppercase">Daemon Health & Diagnostic Checker</h2>
            <p className="text-[#888] text-[10px] tracking-wider mt-0.5">Monitor and restart background SentiNet components</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {eDaemons.map(daemon => {
              const color = statusColor(daemon.status);
              const isRestarting = restarting === daemon.id;
              return (
                <div key={daemon.id} className="bg-white border border-[#cccccc]">
                  <div className="flex items-center justify-between px-4 py-3 border-b border-[#cccccc] bg-[#f5f5f5]">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: color }} />
                      <span className="text-[#0d1b3e] text-[10px] tracking-widest uppercase font-bold">{daemon.name}</span>
                    </div>
                    <span
                      className="text-[9px] tracking-widest font-bold px-2 py-0.5 border"
                      style={{ color, borderColor: color }}
                    >
                      {statusLabel(daemon.status)}
                    </span>
                  </div>
                  <div className="p-4">
                    <p className="text-[#555] text-[10px] tracking-wider font-mono mb-3">{daemon.detail}</p>
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-[#888] text-[9px] tracking-widest">UPTIME: </span>
                        <span className="text-[#0d1b3e] text-[9px] font-mono tracking-wider">{daemon.uptime}</span>
                      </div>
                      <button
                        onClick={() => restartDaemon(daemon.id)}
                        disabled={isRestarting || live}
                        title={live ? 'Service control is managed by the tray daemon' : undefined}
                        className={`flex items-center gap-1.5 text-[9px] tracking-widest uppercase px-3 py-1.5 border transition ${
                          isRestarting || live
                            ? 'border-[#cccccc] text-[#888] cursor-not-allowed'
                            : 'border-[#1a4fd6] text-[#1a4fd6] hover:bg-[#1a4fd6]/10'
                        }`}
                      >
                        <RefreshCw className={`w-3 h-3 ${isRestarting ? 'animate-spin' : ''}`} />
                        {isRestarting ? 'RESTARTING…' : 'RESTART'}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* System summary */}
          <div className="bg-white border border-[#cccccc]">
            <div className="px-4 py-3 border-b border-[#cccccc] bg-[#f5f5f5] flex items-center gap-2">
              <Server className="w-4 h-4 text-[#0d1b3e]" />
              <span className="text-[#0d1b3e] text-[10px] tracking-widest uppercase font-bold">System Summary</span>
            </div>
            <div className="p-4 grid grid-cols-3 gap-4">
              {[
                { label: 'Services Running', value: eDaemons.filter(d => d.status !== 'offline').length, color: '#00aa55' },
                { label: 'Degraded / Offline', value: eDaemons.filter(d => d.status === 'degraded' || d.status === 'offline').length, color: '#c0392b' },
                { label: 'Total Services', value: eDaemons.length, color: '#1a4fd6' },
              ].map(s => (
                <div key={s.label} className="text-center">
                  <p className="text-3xl font-bold tracking-widest" style={{ color: s.color }}>{s.value}</p>
                  <p className="text-[#888] text-[9px] tracking-widest mt-1 uppercase">{s.label}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function PanelHeader({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-2 px-4 py-3 border-b border-[#cccccc] bg-[#f5f5f5]">
      {icon}
      <span className="text-[#0d1b3e] text-[10px] tracking-widest uppercase font-bold">{title}</span>
    </div>
  );
}

function ShieldCheckIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <polyline points="9 12 11 14 15 10" />
    </svg>
  );
}