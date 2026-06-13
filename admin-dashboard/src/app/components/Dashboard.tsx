import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Shield, Activity, Database, Cpu, TerminalSquare, RotateCcw,
  ShieldAlert, Settings, LogOut, Wifi, Lock, Bell, Server, User,
  ToggleLeft, ToggleRight, TrendingUp, Download, Sliders,
} from 'lucide-react';
import { toast, Toaster } from 'sonner';
import ThreatAnalyticsTab, { ThreatDataPoint } from './ThreatAnalyticsTab';
import PolicyTab, { PolicyConfig, AgentHealth } from './PolicyTab';

// ─── Types ────────────────────────────────────────────────────────────────────

type AgentState = 'PROTECTED' | 'DETECTING' | 'SYNCING';

interface Agent {
  id: string;
  name: string;
  ip: string;
  mac: string;
  state: AgentState;
  syncProgress: number;
  cpu: number;
  ram: number;
  connectedSince: string;
  packetsProcessed: number;
}

interface LogEntry    { id: number; timestamp: string; message: string; }
interface LedgerEntry { blockId: string; timestamp: string; macHash: string; score: string; }

type Tab = 'dashboard' | 'analytics' | 'policy' | 'settings';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function now(): string {
  const d = new Date();
  return [d.getHours(), d.getMinutes(), d.getSeconds()].map(n => String(n).padStart(2,'0')).join(':');
}

function randomHex(bytes: number): string {
  return Array.from({ length: bytes }, () => Math.floor(Math.random()*256).toString(16).toUpperCase().padStart(2,'0')).join(':');
}

function generateThreatPoint(prevPPS = 150, attackActive = false): ThreatDataPoint {
  const base   = attackActive ? Math.min(prevPPS + Math.random() * 200, 1800) : Math.max(prevPPS - Math.random() * 80, 30);
  const pps    = Math.round(base + (Math.random() - 0.5) * 60);
  const blocked = Math.round(pps * (0.75 + Math.random() * 0.2));
  return { time: now(), pps: Math.max(10, pps), blocked: Math.min(blocked, pps) };
}

// ─── ToggleRow (settings) ────────────────────────────────────────────────────

function ToggleRow({ label, defaultOn }: { label: string; defaultOn: boolean }) {
  const [on, setOn] = useState(defaultOn);
  return (
    <div className="flex justify-between items-center border-b border-[#E2E8F0] pb-3">
      <span className="text-[#64748B] uppercase tracking-widest text-xs">{label}</span>
      <button onClick={() => setOn(v => !v)} className="flex items-center gap-2 transition-none">
        {on ? <ToggleRight className="w-7 h-7 text-[#1E3A8A]" /> : <ToggleLeft className="w-7 h-7 text-[#94A3B8]" />}
        <span className={`text-xs font-bold uppercase tracking-widest ${on ? 'text-[#1E3A8A]' : 'text-[#94A3B8]'}`}>{on ? 'ON' : 'OFF'}</span>
      </button>
    </div>
  );
}

// ─── CSV Export ───────────────────────────────────────────────────────────────

function exportCSV(ledger: LedgerEntry[]) {
  const header = 'Block ID,Timestamp,Source MAC Hash,Model Confidence\n';
  const rows   = ledger.map(r => `${r.blockId},${r.timestamp},${r.macHash},${r.score}`).join('\n');
  const blob   = new Blob([header + rows], { type: 'text/csv' });
  const url    = URL.createObjectURL(blob);
  const a      = document.createElement('a');
  a.href       = url;
  a.download   = `sentinet-incidents-${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

export default function Dashboard({ onLogout }: { onLogout: () => void }) {
  const logIdCounter   = useRef(4);
  const lastAlertRef   = useRef<number>(0);       // timestamp of last sustained-attack toast
  const prevPPSRef     = useRef(150);
  const attackActiveRef= useRef(false);

  const [activeTab, setActiveTab] = useState<Tab>('dashboard');

  const [agents, setAgents] = useState<Agent[]>([
    { id:'A', name:'Agent Alpha',   ip:'192.168.10.101', mac:'AA:BB:CC:DD:EE:01', state:'PROTECTED', syncProgress:0, cpu:18, ram:42, connectedSince:'08:14:02', packetsProcessed:142830 },
    { id:'B', name:'Agent Bravo',   ip:'192.168.10.102', mac:'AA:BB:CC:DD:EE:02', state:'PROTECTED', syncProgress:0, cpu:22, ram:51, connectedSince:'08:14:07', packetsProcessed:138420 },
    { id:'C', name:'Agent Charlie', ip:'192.168.10.103', mac:'AA:BB:CC:DD:EE:03', state:'PROTECTED', syncProgress:0, cpu:15, ram:37, connectedSince:'08:15:11', packetsProcessed:159012 },
    { id:'D', name:'Agent Delta',   ip:'192.168.10.104', mac:'AA:BB:CC:DD:EE:04', state:'PROTECTED', syncProgress:0, cpu:31, ram:58, connectedSince:'08:15:33', packetsProcessed:121765 },
  ]);

  const [logs, setLogs] = useState<LogEntry[]>([
    { id:1, timestamp:'14:30:00', message:'SYSTEM: POC-Control-Hub Initialized.' },
    { id:2, timestamp:'14:30:02', message:'NETWORK: MultiChain connected successfully.' },
    { id:3, timestamp:'14:30:05', message:'SOCKET: Listening on port 8080.' },
  ]);

  const [ledger, setLedger] = useState<LedgerEntry[]>([
    { blockId:'0x8A12', timestamp:'14:28:11', macHash:'FD:09:A1:XX', score:'98.2%' },
    { blockId:'0x8A13', timestamp:'14:29:05', macHash:'E2:11:4B:XX', score:'94.5%' },
  ]);

  const [telemetry, setTelemetry] = useState({ cpu: 12, ram: 44, latency: 14 });

  const [blockchainMetrics, setBlockchainMetrics] = useState({
    blockHeight:    33912,
    lastSyncTime:   now(),
    chainStatus:    'HEALTHY' as 'HEALTHY' | 'DEGRADED',
    totalIncidents: 47,
  });

  const [threatHistory, setThreatHistory] = useState<ThreatDataPoint[]>(() =>
    Array.from({ length: 20 }, (_, i) => ({
      time:    `${String(14 + Math.floor(i / 4)).padStart(2,'0')}:${String((i * 15) % 60).padStart(2,'0')}:00`,
      pps:     Math.floor(Math.random() * 180) + 40,
      blocked: Math.floor(Math.random() * 140) + 30,
    }))
  );

  const [policyConfig, setPolicyConfig] = useState<PolicyConfig>({
    mlThreshold:      0.50,
    arpFloodLimit:    1000,
    autoBlacklist:    false,
    syncInterval:     4000,
    logRetentionDays: 30,
  });

  const logEndRef    = useRef<HTMLDivElement>(null);
  const ledgerTopRef = useRef<HTMLTableRowElement>(null);
  const pageTopRef   = useRef<HTMLDivElement>(null);
  const pageBottomRef= useRef<HTMLDivElement>(null);

  // Auto-scroll log to bottom
  useEffect(() => { logEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [logs]);
  // Auto-scroll ledger to top (newest first)
  useEffect(() => { ledgerTopRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }, [ledger]);

  // ── Main simulation interval ───────────────────────────────────────────────
  useEffect(() => {
    const sim = setInterval(() => {

      // Threat history + sustained-attack detection
      setThreatHistory(prev => {
        const lastPPS  = prev[prev.length - 1]?.pps ?? 150;
        const isAttack = attackActiveRef.current;
        const point    = generateThreatPoint(lastPPS, isAttack);
        prevPPSRef.current = point.pps;

        // Sustained-attack toast: PPS > arpFloodLimit and cooldown 20s
        if (point.pps >= policyConfig.arpFloodLimit) {
          const elapsed = Date.now() - lastAlertRef.current;
          if (elapsed > 20_000) {
            lastAlertRef.current = Date.now();
            toast.error(
              `CRITICAL: ARP Flood Detected — ${point.pps.toLocaleString()} PPS (limit: ${policyConfig.arpFloodLimit})`,
              {
                duration: 8000,
                style: {
                  background: '#0F172A',
                  border: '2px solid #DC2626',
                  color: '#fff',
                  borderRadius: 0,
                  fontFamily: 'JetBrains Mono, monospace',
                  fontSize: '12px',
                },
              }
            );
          }
        }
        return [...prev.slice(-29), point];
      });

      // Agent simulation
      setAgents(prev => {
        const next = [...prev];
        const protected_ = next.filter(a => a.state === 'PROTECTED');

        if (protected_.length > 0 && Math.random() > 0.7) {
          const target = protected_[Math.floor(Math.random() * protected_.length)];
          const idx    = next.findIndex(a => a.id === target.id);
          next[idx] = { ...target, state: 'DETECTING' };
          attackActiveRef.current = true;

          const ts = now();
          setLogs(l => [...l, { id: logIdCounter.current++, timestamp: ts, message: `ALERT: ${target.name} detected ARP Spoofing. Broadcasting MAC to network...` }].slice(-100));

          setTimeout(() => {
            setAgents(cur => {
              const u = [...cur];
              const i = u.findIndex(a => a.id === target.id);
              if (i > -1) u[i] = { ...u[i], state: 'SYNCING', syncProgress: 0 };
              return u;
            });

            let prog = 0;
            const progInt = setInterval(() => {
              prog += 15;
              if (prog >= 100) {
                clearInterval(progInt);
                attackActiveRef.current = false;
                setAgents(cur => {
                  const u = [...cur];
                  const i = u.findIndex(a => a.id === target.id);
                  if (i > -1) u[i] = { ...u[i], state: 'PROTECTED', syncProgress: 0 };
                  return u;
                });
                const ts2 = now();
                setLogs(l => [...l, { id: logIdCounter.current++, timestamp: ts2, message: `SYSTEM: ${target.name} Bayanihan Sync complete. Threat isolated.` }].slice(-100));
                setLedger(lg => [{
                  blockId:   `0x${Math.floor(Math.random()*65536).toString(16).toUpperCase().padStart(4,'0')}`,
                  timestamp: ts2,
                  macHash:   `${randomHex(2)}:XX:XX`,
                  score:     `${(Math.random()*5+94).toFixed(1)}%`,
                }, ...lg.slice(0, 19)]);
                setBlockchainMetrics(m => ({
                  ...m,
                  blockHeight:    m.blockHeight + 1,
                  lastSyncTime:   ts2,
                  totalIncidents: m.totalIncidents + 1,
                }));
              } else {
                setAgents(cur => {
                  const u = [...cur];
                  const i = u.findIndex(a => a.id === target.id);
                  if (i > -1) u[i] = { ...u[i], syncProgress: prog };
                  return u;
                });
              }
            }, 300);
          }, 3000);
        }

        // Update per-agent CPU/RAM
        return next.map(a => ({
          ...a,
          cpu: a.state === 'DETECTING'
            ? Math.min(a.cpu + Math.floor(Math.random() * 30) + 15, 98)
            : Math.max(10, Math.floor(Math.random() * 30) + 12),
          ram: Math.max(30, Math.floor(Math.random() * 20) + 40),
          packetsProcessed: a.packetsProcessed + Math.floor(Math.random() * 800) + 200,
        }));
      });

      setTelemetry({
        cpu:     Math.floor(Math.random() * 25) + 10,
        ram:     Math.floor(Math.random() * 15) + 40,
        latency: Math.floor(Math.random() * 8)  + 12,
      });
    }, 4000);

    return () => clearInterval(sim);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [policyConfig.arpFloodLimit]);

  // ── Action handlers ────────────────────────────────────────────────────────

  const handleManualBlacklist = () => {
    const ts = now();
    setLogs(l => [...l, { id: logIdCounter.current++, timestamp: ts, message: 'ADMIN: Manual Blacklist Injection executed (SOP 3).' }]);
    setLedger(lg => [{
      blockId: `0x${Math.floor(Math.random()*65536).toString(16).toUpperCase().padStart(4,'0')}`,
      timestamp: ts, macHash: 'FF:FF:FF:XX', score: '100.0%',
    }, ...lg.slice(0,19)]);
    toast('Manual Blacklist Injection executed.', {
      style: { background: '#0F172A', border: '2px solid #1E3A8A', color: '#fff', borderRadius: 0, fontFamily: 'JetBrains Mono, monospace', fontSize: '12px' },
      duration: 4000,
    });
  };

  const handleFlush = () => {
    const ts = now();
    setLogs([{ id: logIdCounter.current++, timestamp: ts, message: 'SYSTEM: Network-Wide Flush triggered. Ledger state cleared.' }]);
    setLedger([]);
  };

  const handlePolicyBroadcast = useCallback((cfg: PolicyConfig, changes: string[]) => {
    setPolicyConfig(cfg);
    const ts = now();
    changes.forEach(ch => {
      setLogs(l => [...l, { id: logIdCounter.current++, timestamp: ts, message: `POLICY: Broadcast — ${ch}` }].slice(-100));
    });
    toast.success(
      `Policy broadcast to ${agents.length} agents — ${changes.length} change${changes.length > 1 ? 's' : ''} applied`,
      {
        style: { background: '#0F172A', border: '2px solid #16A34A', color: '#fff', borderRadius: 0, fontFamily: 'JetBrains Mono, monospace', fontSize: '12px' },
        duration: 5000,
      }
    );
  }, [agents.length]);

  const agentHealthData: AgentHealth[] = agents.map(a => ({
    id:               a.id,
    name:             a.name,
    ip:               a.ip,
    mac:              a.mac,
    cpu:              a.cpu,
    ram:              a.ram,
    connectedSince:   a.connectedSince,
    packetsProcessed: a.packetsProcessed,
    state:            a.state,
  }));

  const TABS: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: 'dashboard', label: 'Dashboard',  icon: <Activity className="w-4 h-4" /> },
    { key: 'analytics', label: 'Analytics',  icon: <TrendingUp className="w-4 h-4" /> },
    { key: 'policy',    label: 'Policy',     icon: <Sliders className="w-4 h-4" /> },
    { key: 'settings',  label: 'Settings',   icon: <Settings className="w-4 h-4" /> },
  ];

  return (
    <div className="min-h-screen w-full bg-[#E2E8F0] flex flex-col p-4 font-['Inter',_sans-serif] text-slate-900 gap-4 box-border antialiased">
      {/* Toaster for push notifications */}
      <Toaster position="top-right" />

      <div ref={pageTopRef} />

      {/* Floating scroll buttons */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2">
        <button onClick={() => pageTopRef.current?.scrollIntoView({ behavior: 'smooth' })} className="w-11 h-11 bg-[#1E3A8A] border-2 border-[#334155] text-white flex items-center justify-center hover:bg-[#1e40af] transition-none" title="Scroll to Top">
          <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="square"><polyline points="18 15 12 9 6 15"/></svg>
        </button>
        <button onClick={() => pageBottomRef.current?.scrollIntoView({ behavior: 'smooth' })} className="w-11 h-11 bg-[#1E3A8A] border-2 border-[#334155] text-white flex items-center justify-center hover:bg-[#1e40af] transition-none" title="Scroll to Bottom">
          <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="square"><polyline points="6 9 12 15 18 9"/></svg>
        </button>
      </div>

      {/* Header */}
      <header className="flex justify-between items-center bg-[#1E3A8A] text-white p-4 border-2 border-[#334155] uppercase tracking-wide font-bold shrink-0">
        <div className="flex items-center gap-3">
          <Shield className="w-6 h-6" fill="white" />
          <span className="text-xl tracking-widest">Relay Node: POC-Control-Hub</span>
        </div>
        <div className="flex items-center gap-8 text-sm font-['JetBrains_Mono',_monospace]">
          <span className="flex items-center gap-2"><div className="w-3 h-3 bg-[#16A34A] border border-[#334155]" />MultiChain: Active</span>
          <span className="flex items-center gap-2"><div className="w-3 h-3 bg-[#16A34A] border border-[#334155]" />WebSocket: Listening</span>
          <span className="flex items-center gap-2"><Activity className="w-4 h-4" />Sync Latency: {telemetry.latency}ms</span>
        </div>
      </header>

      {/* Tab Bar */}
      <div className="flex border-2 border-[#334155] shrink-0 bg-[#F1F5F9]">
        {TABS.map((tab, i) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-2 px-6 py-3 text-sm font-bold uppercase tracking-widest border-r-2 border-[#334155] transition-none ${activeTab === tab.key ? 'bg-[#1E3A8A] text-white' : 'bg-transparent text-[#475569] hover:bg-[#E2E8F0]'}`}
          >
            {tab.icon}{tab.label}
          </button>
        ))}
        <div className="flex-1" />
        <button onClick={onLogout} className="flex items-center gap-2 px-6 py-3 text-sm font-bold uppercase tracking-widest text-[#DC2626] hover:bg-[#DC2626] hover:text-white border-l-2 border-[#334155] transition-none">
          <LogOut className="w-4 h-4" />Logout
        </button>
      </div>

      {/* ── Analytics Tab ── */}
      {activeTab === 'analytics' && (
        <ThreatAnalyticsTab data={threatHistory} arpFloodLimit={policyConfig.arpFloodLimit} />
      )}

      {/* ── Policy Tab ── */}
      {activeTab === 'policy' && (
        <PolicyTab config={policyConfig} agents={agentHealthData} onBroadcast={handlePolicyBroadcast} />
      )}

      {/* ── Settings Tab ── */}
      {activeTab === 'settings' && (
        <div className="flex flex-col gap-4">
          <section className="border-2 border-[#334155] bg-white">
            <div className="bg-[#F1F5F9] border-b-2 border-[#334155] p-3 px-4 font-bold uppercase text-sm tracking-widest flex items-center gap-2 text-[#0F172A]"><User className="w-5 h-5" />Admin Profile</div>
            <div className="p-6 grid grid-cols-2 gap-6 font-['JetBrains_Mono',_monospace] text-sm">
              {[
                { label:'Digital ID',       value:'ADM-7734-ALPHA' },
                { label:'Clearance Level',  value:'OMEGA-5' },
                { label:'Role',             value:'Network Security Administrator' },
                { label:'Last Login',       value:'2049-03-14  08:42:11 UTC' },
                { label:'Session Token',    value:'eyJ0eXAiOiJKV1QiLCJhb...' },
                { label:'MFA Method',       value:'OTP + FINGERPRINT' },
              ].map(row => (
                <div key={row.label} className="flex flex-col gap-1 border-b border-[#E2E8F0] pb-3">
                  <span className="text-[#94A3B8] text-xs uppercase tracking-widest">{row.label}</span>
                  <span className="text-[#0F172A] font-bold truncate">{row.value}</span>
                </div>
              ))}
            </div>
          </section>
          <div className="grid grid-cols-2 gap-4">
            <section className="border-2 border-[#334155] bg-white">
              <div className="bg-[#F1F5F9] border-b-2 border-[#334155] p-3 px-4 font-bold uppercase text-sm tracking-widest flex items-center gap-2 text-[#0F172A]"><Wifi className="w-5 h-5" />Network Configuration</div>
              <div className="p-5 space-y-4 font-['JetBrains_Mono',_monospace] text-sm">
                {[
                  { label:'Control Hub IP',     value:'192.168.10.1' },
                  { label:'Subnet Mask',         value:'255.255.255.0' },
                  { label:'Gateway',             value:'192.168.10.254' },
                  { label:'WebSocket Port',      value:'8080' },
                  { label:'MultiChain RPC Port', value:'15590' },
                  { label:'Sync Interval',       value:`${policyConfig.syncInterval} ms` },
                ].map(row => (
                  <div key={row.label} className="flex justify-between border-b border-[#E2E8F0] pb-3">
                    <span className="text-[#64748B] uppercase tracking-widest text-xs self-center">{row.label}</span>
                    <input className="bg-[#F8FAFC] border-2 border-[#E2E8F0] px-3 py-1 text-[#0F172A] font-bold text-xs w-44 focus:outline-none focus:border-[#1E3A8A]" defaultValue={row.value} />
                  </div>
                ))}
              </div>
            </section>
            <section className="border-2 border-[#334155] bg-white">
              <div className="bg-[#F1F5F9] border-b-2 border-[#334155] p-3 px-4 font-bold uppercase text-sm tracking-widest flex items-center gap-2 text-[#0F172A]"><Bell className="w-5 h-5" />Security &amp; Alerts</div>
              <div className="p-5 space-y-4 font-['JetBrains_Mono',_monospace] text-sm">
                {[
                  { label:'ARP Spoof Detection',      on:true  },
                  { label:'Rogue AP Alerts',           on:true  },
                  { label:'Auto-Blacklist on Threat',  on:policyConfig.autoBlacklist },
                  { label:'Bayanihan Sync Alerts',     on:true  },
                  { label:'Chain Write Notifications', on:false },
                  { label:'Email Alerts',              on:true  },
                ].map(row => <ToggleRow key={row.label} label={row.label} defaultOn={row.on} />)}
              </div>
            </section>
          </div>
          <section className="border-2 border-[#334155] bg-white">
            <div className="bg-[#F1F5F9] border-b-2 border-[#334155] p-3 px-4 font-bold uppercase text-sm tracking-widest flex items-center gap-2 text-[#0F172A]"><Server className="w-5 h-5" />System Information</div>
            <div className="p-5 grid grid-cols-4 gap-4 font-['JetBrains_Mono',_monospace] text-sm">
              {[
                { label:'POC Version',     value:'v2.4.9' },
                { label:'OS',              value:'SentiOS 4.1 LTS' },
                { label:'Node Runtime',    value:'Node.js 20.11.0' },
                { label:'MultiChain',      value:'v2.3.3' },
                { label:'Uptime',          value:'14d 06h 32m' },
                { label:'Disk Usage',      value:'38.4 GB / 512 GB' },
                { label:'Active Sessions', value:'1 (ADM-7734)' },
                { label:'Chain Height',    value:`#${String(blockchainMetrics.blockHeight).padStart(8,'0')}` },
              ].map(row => (
                <div key={row.label} className="border-2 border-[#E2E8F0] p-4 flex flex-col gap-1">
                  <span className="text-[#94A3B8] text-[10px] uppercase tracking-widest">{row.label}</span>
                  <span className="text-[#0F172A] font-bold text-xs">{row.value}</span>
                </div>
              ))}
            </div>
          </section>
          <section className="border-2 border-[#DC2626] bg-white">
            <div className="bg-[#DC2626] border-b-2 border-[#DC2626] p-3 px-4 font-bold uppercase text-sm tracking-widest flex items-center gap-2 text-white"><Lock className="w-5 h-5" />Danger Zone</div>
            <div className="p-5 flex flex-wrap gap-4">
              {['Revoke All Sessions','Reset Agent Registry','Wipe Blockchain Cache','Factory Reset Node'].map(action => (
                <button key={action} className="border-2 border-[#DC2626] text-[#DC2626] px-5 py-3 text-xs font-bold uppercase tracking-widest hover:bg-[#DC2626] hover:text-white transition-none font-['JetBrains_Mono',_monospace]">{action}</button>
              ))}
              <button onClick={onLogout} className="border-2 border-[#DC2626] bg-[#DC2626] text-white px-5 py-3 text-xs font-bold uppercase tracking-widest hover:bg-[#b91c1c] transition-none font-['JetBrains_Mono',_monospace] flex items-center gap-2 ml-auto">
                <LogOut className="w-4 h-4" />Logout &amp; End Session
              </button>
            </div>
          </section>
        </div>
      )}

      {/* ── Dashboard Tab ── */}
      {activeTab === 'dashboard' && <>

        {/* Agent Status Grid */}
        <section className="shrink-0 border-2 border-[#334155] bg-white flex flex-col" style={{ minHeight: 200 }}>
          <div className="bg-[#F1F5F9] border-b-2 border-[#334155] p-3 px-4 font-bold uppercase text-sm tracking-widest text-[#0F172A] flex items-center gap-2 shrink-0">
            <Shield className="w-5 h-5" />Agent Status Overview
            <span className="ml-auto font-['JetBrains_Mono',_monospace] text-[#16A34A] text-xs">
              {agents.filter(a => a.state === 'PROTECTED').length}/{agents.length} PROTECTED
            </span>
          </div>
          <div className="overflow-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead className="bg-[#F8FAFC] border-b-2 border-[#334155] sticky top-0 z-10 font-bold uppercase tracking-widest text-xs">
                <tr>
                  <th className="p-3 border-r-2 border-[#334155] text-[#0F172A]">ID</th>
                  <th className="p-3 border-r-2 border-[#334155] text-[#0F172A]">Name</th>
                  <th className="p-3 border-r-2 border-[#334155] text-[#0F172A]">IP Address</th>
                  <th className="p-3 border-r-2 border-[#334155] text-[#0F172A]">MAC Address</th>
                  <th className="p-3 border-r-2 border-[#334155] text-[#0F172A]">CPU / RAM</th>
                  <th className="p-3 text-[#0F172A]">Status</th>
                </tr>
              </thead>
              <tbody>
                {agents.map(agent => (
                  <tr key={agent.id} className="border-b border-[#334155] hover:bg-slate-50 transition-none">
                    <td className="p-3 border-r-2 border-[#334155] font-['JetBrains_Mono',_monospace] font-bold opacity-60">{agent.id}</td>
                    <td className="p-3 border-r-2 border-[#334155] font-bold uppercase tracking-tight">{agent.name}</td>
                    <td className="p-3 border-r-2 border-[#334155] font-['JetBrains_Mono',_monospace]">{agent.ip}</td>
                    <td className="p-3 border-r-2 border-[#334155] font-['JetBrains_Mono',_monospace]">{agent.mac}</td>
                    <td className="p-3 border-r-2 border-[#334155]">
                      <div className="flex flex-col gap-1 w-36">
                        <div className="flex justify-between text-[9px] font-bold uppercase">
                          <span>CPU</span>
                          <span className={`font-['JetBrains_Mono',_monospace] ${agent.cpu > 70 ? 'text-[#DC2626]' : 'text-[#0F172A]'}`}>{agent.cpu}%</span>
                        </div>
                        <div className="h-1.5 border border-[#334155] bg-white">
                          <div className={`h-full transition-all duration-500 ${agent.cpu > 70 ? 'bg-[#DC2626]' : 'bg-[#1E3A8A]'}`} style={{ width: `${agent.cpu}%` }} />
                        </div>
                        <div className="flex justify-between text-[9px] font-bold uppercase">
                          <span>RAM</span>
                          <span className="font-['JetBrains_Mono',_monospace] text-[#0F172A]">{agent.ram}%</span>
                        </div>
                        <div className="h-1.5 border border-[#334155] bg-white">
                          <div className="h-full bg-[#16A34A] transition-all duration-500" style={{ width: `${agent.ram}%` }} />
                        </div>
                      </div>
                    </td>
                    <td className={`p-3 font-black uppercase tracking-widest w-64 ${agent.state === 'PROTECTED' ? 'text-[#16A34A] bg-[#F1F5F9]' : ''} ${agent.state === 'DETECTING' ? 'text-white bg-[#DC2626] animate-pulse' : ''} ${agent.state === 'SYNCING' ? 'bg-[#F1F5F9]' : ''}`}>
                      {agent.state === 'PROTECTED' && 'PROTECTED'}
                      {agent.state === 'DETECTING' && <div className="flex items-center gap-2"><ShieldAlert className="w-5 h-5" />ATTACK DETECTED</div>}
                      {agent.state === 'SYNCING' && (
                        <div>
                          <div className="flex justify-between text-[10px] text-[#0F172A] mb-1"><span>BAYANIHAN SYNCING</span><span className="font-['JetBrains_Mono',_monospace]">{agent.syncProgress}%</span></div>
                          <div className="w-full h-3 border-2 border-[#334155] bg-white p-0.5">
                            <div className="h-full bg-[#1E3A8A] transition-all duration-300" style={{ width: `${agent.syncProgress}%` }} />
                          </div>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Live Intelligence Stream */}
        <section className="border-2 border-[#334155] bg-white flex flex-col" style={{ minHeight: 200, maxHeight: 300 }}>
          <div className="bg-[#F1F5F9] border-b-2 border-[#334155] p-3 px-4 font-bold uppercase text-sm tracking-widest text-[#0F172A] flex justify-between items-center shrink-0">
            <span>Live Intelligence Stream (Socket.io)</span>
            <TerminalSquare className="w-5 h-5" />
          </div>
          <div className="flex-1 overflow-y-auto p-4 font-['JetBrains_Mono',_monospace] text-sm bg-white text-slate-800 flex flex-col gap-2">
            {logs.map(log => (
              <div key={log.id} className="border-b border-slate-200 pb-2">
                <span className="text-slate-500 mr-2">[{log.timestamp}]</span>
                <span className={`${log.message.startsWith('ALERT') ? 'text-[#DC2626] font-bold' : ''} ${log.message.startsWith('ADMIN') ? 'text-[#1E3A8A] font-bold' : ''} ${log.message.startsWith('POLICY') ? 'text-[#7C3AED] font-bold' : ''}`}>
                  {log.message}
                </span>
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        </section>

        {/* Bottom row: Blockchain + Telemetry */}
        <section className="grid grid-cols-2 gap-4 shrink-0">

          {/* Blockchain Ledger + Metrics */}
          <div className="border-2 border-[#334155] bg-white flex flex-col">
            <div className="bg-[#F1F5F9] border-b-2 border-[#334155] p-3 px-4 font-bold uppercase text-sm tracking-widest flex items-center gap-2 text-[#0F172A] shrink-0">
              <Database className="w-5 h-5" />Blockchain Ledger (MultiChain)
              <button
                onClick={() => exportCSV(ledger)}
                className="ml-auto flex items-center gap-1 px-3 py-1 border-2 border-[#334155] text-[10px] font-bold uppercase tracking-widest hover:bg-[#1E3A8A] hover:text-white hover:border-[#1E3A8A] transition-none"
              >
                <Download className="w-3 h-3" />Export CSV
              </button>
            </div>

            {/* Blockchain metrics strip */}
            <div className="grid grid-cols-4 border-b-2 border-[#334155] font-['JetBrains_Mono',_monospace]">
              {[
                { label:'Block Height',    value:`#${String(blockchainMetrics.blockHeight).padStart(8,'0')}` },
                { label:'Chain Status',    value:blockchainMetrics.chainStatus, ok: blockchainMetrics.chainStatus === 'HEALTHY' },
                { label:'Last Sync',       value:blockchainMetrics.lastSyncTime },
                { label:'Total Incidents', value:String(blockchainMetrics.totalIncidents) },
              ].map(m => (
                <div key={m.label} className="p-3 border-r border-[#E2E8F0] last:border-r-0 flex flex-col gap-0.5">
                  <span className="text-[9px] uppercase tracking-widest text-[#94A3B8]">{m.label}</span>
                  <span className={`text-xs font-bold ${'ok' in m ? (m.ok ? 'text-[#16A34A]' : 'text-[#DC2626]') : 'text-[#0F172A]'}`}>{m.value}</span>
                </div>
              ))}
            </div>

            <div className="flex-1 overflow-auto" style={{ maxHeight: 180 }}>
              <table className="w-full text-left border-collapse font-['JetBrains_Mono',_monospace] text-sm">
                <thead className="bg-[#F8FAFC] border-b-2 border-[#334155] sticky top-0 z-10">
                  <tr>
                    <th className="p-3 border-r-2 border-[#334155] font-bold text-[#0F172A]">Block ID</th>
                    <th className="p-3 border-r-2 border-[#334155] font-bold text-[#0F172A]">Timestamp</th>
                    <th className="p-3 border-r-2 border-[#334155] font-bold text-[#0F172A]">Source MAC Hash</th>
                    <th className="p-3 font-bold text-[#0F172A]">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {ledger.map((row, i) => (
                    <tr key={row.blockId} ref={i === 0 ? ledgerTopRef : null} className="border-b border-[#334155] hover:bg-slate-50 transition-none">
                      <td className="p-3 border-r-2 border-[#334155]">{row.blockId}</td>
                      <td className="p-3 border-r-2 border-[#334155]">{row.timestamp}</td>
                      <td className="p-3 border-r-2 border-[#334155] font-bold">{row.macHash}</td>
                      <td className="p-3 text-[#16A34A] font-bold">{row.score}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Relay Telemetry */}
          <div className="border-2 border-[#334155] bg-white flex flex-col">
            <div className="bg-[#F1F5F9] border-b-2 border-[#334155] p-3 px-4 font-bold uppercase text-sm tracking-widest flex items-center gap-2 text-[#0F172A] shrink-0">
              <Cpu className="w-5 h-5" />Relay Telemetry &amp; Governance
            </div>
            <div className="flex-1 p-5 flex flex-col gap-5 justify-between">
              <div className="flex gap-6">
                <div className="flex-1 flex flex-col gap-2">
                  <div className="flex justify-between text-sm font-bold uppercase"><span>Relay Node CPU</span><span className="font-['JetBrains_Mono',_monospace]">{telemetry.cpu}%</span></div>
                  <div className="w-full h-8 border-2 border-[#334155] p-1 bg-[#F1F5F9]">
                    <div className="h-full bg-[#1E3A8A] transition-all duration-500" style={{ width: `${telemetry.cpu}%` }} />
                  </div>
                </div>
                <div className="flex-1 flex flex-col gap-2">
                  <div className="flex justify-between text-sm font-bold uppercase"><span>RAM Allocation</span><span className="font-['JetBrains_Mono',_monospace]">{telemetry.ram}%</span></div>
                  <div className="w-full h-8 border-2 border-[#334155] p-1 bg-[#F1F5F9]">
                    <div className="h-full bg-[#1E3A8A] transition-all duration-500" style={{ width: `${telemetry.ram}%` }} />
                  </div>
                </div>
              </div>

              {/* ML Threshold live indicator */}
              <div className="border-2 border-[#E2E8F0] p-3 flex justify-between items-center font-['JetBrains_Mono',_monospace] text-xs">
                <span className="text-[#64748B] uppercase tracking-widest">ML Confidence Threshold</span>
                <span className="font-bold text-[#1E3A8A]">{policyConfig.mlThreshold.toFixed(2)}</span>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <button onClick={handleManualBlacklist} className="bg-[#0F172A] hover:bg-[#1E293B] text-white border-2 border-[#0F172A] p-4 uppercase font-bold text-sm tracking-widest flex justify-center items-center gap-2 active:bg-black transition-none">
                  <ShieldAlert className="w-5 h-5" />Manual Blacklist
                </button>
                <button onClick={handleFlush} className="bg-white hover:bg-[#F1F5F9] text-[#DC2626] border-2 border-[#DC2626] p-4 uppercase font-bold text-sm tracking-widest flex justify-center items-center gap-2 active:bg-red-50 transition-none">
                  <RotateCcw className="w-5 h-5" />Network-Wide Flush
                </button>
              </div>
            </div>
          </div>
        </section>

        <div ref={pageBottomRef} />
      </>}

    </div>
  );
}
