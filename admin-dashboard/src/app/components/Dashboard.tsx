import React, { useState, useEffect, useRef, useLayoutEffect } from 'react';
import { toast, Toaster } from 'sonner';
import ThreatAnalyticsTab, { ThreatDataPoint } from './ThreatAnalyticsTab';
import SopTab from './SopTab';
import { getAdminDashboardSeed, getAdminDashboardSeedFallback } from '../lib/adminApi';
import type { AdminBlacklistEntry, AdminPolicyConfig } from '../lib/adminApi';

// ─── Types ────────────────────────────────────────────────────────────────────

type AgentState = 'PROTECTED' | 'DETECTING' | 'SYNCING' | 'UNPROTECTED';

interface Agent {
  id: string;
  name: string;
  ip: string;
  mac: string;
  state: AgentState;
  syncProgress: number;
  cpu: number;
  ram: number;
  ramMb?: number | null;
  ramProcessPercent?: number | null;
  connectedSince: string;
  packetsProcessed: number;
}

interface LogEntry    { id: number; timestamp: string; message: string; }
interface LedgerEntry { blockId: string; timestamp: string; macHash: string; score: string; }

type Tab = 'dashboard' | 'analytics' | 'sop';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function now(): string {
  const d = new Date();
  return [d.getHours(), d.getMinutes(), d.getSeconds()].map(n => String(n).padStart(2,'0')).join(':');
}

function randomHex(bytes: number): string {
  // Replace random with simple hex based on timestamp for POC
  return Array.from({ length: bytes }, (_, i) => ((Date.now() + i) % 256).toString(16).toUpperCase().padStart(2,'0')).join(':');
}

// ─── CSV Export ───────────────────────────────────────────────────────────────

function exportCSV(ledger: LedgerEntry[]) {
  const header = 'BlockChain ID,Timestamp,Source MAC Hash,Model Confidence\n';
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
  const [adminSeed, setAdminSeed] = useState(() => getAdminDashboardSeedFallback());
  const logIdCounter   = useRef(4);
  const lastAlertRef   = useRef<number>(0);       // timestamp of last sustained-attack toast
  const prevPPSRef     = useRef(150);
  const attackActiveRef= useRef(false);

  const [activeTab, setActiveTab] = useState<Tab>('dashboard');

  const [agents, setAgents] = useState<Agent[]>(adminSeed.agents);

  const [logs, setLogs] = useState<LogEntry[]>(adminSeed.logs);

  const [ledger, setLedger] = useState<LedgerEntry[]>(adminSeed.ledger);

  const [blacklist, setBlacklist] = useState<AdminBlacklistEntry[]>(adminSeed.blacklist);

  const [telemetry, setTelemetry] = useState(adminSeed.telemetry);

  const [blockchainMetrics, setBlockchainMetrics] = useState({
    ...adminSeed.blockchainMetrics,
    lastSyncTime: adminSeed.blockchainMetrics.lastSyncTime,
  });

  const [threatHistory, setThreatHistory] = useState<ThreatDataPoint[]>(adminSeed.threatHistory);

  const [policyConfig, setPolicyConfig] = useState<AdminPolicyConfig>(adminSeed.policyConfig);

  const logsContainerRef = useRef<HTMLDivElement>(null);
  const ledgerContainerRef = useRef<HTMLDivElement>(null);
  const prevLogsSnapshotRef = useRef<{ length: number; scrollTop: number; scrollHeight: number; clientHeight: number } | null>(null);
  const prevLedgerSnapshotRef = useRef<{ length: number; scrollTop: number; scrollHeight: number; clientHeight: number } | null>(null);

  useEffect(() => {
    let alive = true;
    void (async () => {
      const seed = await getAdminDashboardSeed();
      if (!alive) return;
      setAdminSeed(seed);
      setAgents(seed.agents);
      setLogs(seed.logs);
      setLedger(seed.ledger);
      setBlacklist(seed.blacklist);
      setTelemetry(seed.telemetry);
      setBlockchainMetrics(seed.blockchainMetrics);
      setThreatHistory(seed.threatHistory);
      setPolicyConfig(seed.policyConfig);
    })();

    return () => {
      alive = false;
    };
  }, []);

  useLayoutEffect(() => {
    const c = logsContainerRef.current;
    const prev = prevLogsSnapshotRef.current;
    if (!c) { prevLogsSnapshotRef.current = null; return; }
    if (!prev) { prevLogsSnapshotRef.current = { length: logs.length, scrollTop: c.scrollTop, scrollHeight: c.scrollHeight, clientHeight: c.clientHeight }; return; }
    prevLogsSnapshotRef.current = { length: logs.length, scrollTop: c.scrollTop, scrollHeight: c.scrollHeight, clientHeight: c.clientHeight };
  }, [logs]);

  useLayoutEffect(() => {
    const c = ledgerContainerRef.current;
    const prev = prevLedgerSnapshotRef.current;
    const threshold = 40;
    if (!c) { prevLedgerSnapshotRef.current = null; return; }

    if (!prev) {
      prevLedgerSnapshotRef.current = { length: ledger.length, scrollTop: c.scrollTop, scrollHeight: c.scrollHeight, clientHeight: c.clientHeight };
      return;
    }

    const prevLen = prev.length;
    const prevScrollHeight = prev.scrollHeight;
    const prevScrollTop = prev.scrollTop;

    if (ledger.length > prevLen) {
      const delta = c.scrollHeight - prevScrollHeight;
      const wasAtTop = (prevScrollTop <= threshold);
      if (wasAtTop) {
        c.scrollTop = 0;
      } else if (delta > 0) {
        c.scrollTop = prevScrollTop + delta;
      }
    }

    prevLedgerSnapshotRef.current = { length: ledger.length, scrollTop: c.scrollTop, scrollHeight: c.scrollHeight, clientHeight: c.clientHeight };
  }, [ledger]);

  // ── Main polling interval ───────────────────────────────────────────────
  useEffect(() => {
    let alive = true;
    const poll = setInterval(async () => {
      try {
        const seed = await getAdminDashboardSeed();
        if (!alive) return;
        setAgents(seed.agents);
        setLedger(seed.ledger);
      setBlacklist(seed.blacklist);
        setTelemetry(seed.telemetry);
        setBlockchainMetrics(seed.blockchainMetrics);
        setThreatHistory(seed.threatHistory);
        setPolicyConfig(seed.policyConfig);
        
        // Let's only update logs if they are significantly different to avoid overwriting manual local logs completely
        // For POC, we will just use backend logs + local logs
        setLogs(prev => {
           // simple merge or just use backend
           return seed.logs.length > 0 ? seed.logs : prev;
        });
      } catch (err) {
        console.error("Polling failed", err);
      }
    }, 2000);

    return () => {
      alive = false;
      clearInterval(poll);
    };
  }, []);

  // ── Action handlers ────────────────────────────────────────────────────────

  const handleManualBlacklist = () => {
    const ts = now();
    setLogs(l => [...l, { id: logIdCounter.current++, timestamp: ts, message: 'ADMIN: Manual Blacklist Injection executed (SOP 3).' }]);
    setLedger(lg => [{
      blockId: `0x${(Date.now() % 65536).toString(16).toUpperCase().padStart(4,'0')}`,
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

  const TABS: { key: Tab; label: string }[] = [
    { key: 'dashboard', label: 'Dashboard' },
    { key: 'analytics', label: 'Analytics' },
    { key: 'sop',       label: 'SOP' },
  ];

  return (
    <div className="min-h-screen bg-[#e8eaed] flex flex-col text-slate-900 antialiased">
      {/* Toaster for push notifications */}
      <Toaster position="top-right" />

      {/* Header */}
      <header className="bg-[#0d1b3e] border-b-2 border-[#c0392b] px-6 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-white tracking-widest text-sm font-bold uppercase">Admin Sentinet</span>
        </div>
        <div className="flex items-center gap-6 text-xs text-[#8899bb]">
          <span className="flex items-center gap-2">
            <div className={`w-2.5 h-2.5 rounded-sm ${blockchainMetrics.connectedAgents > 0 ? 'bg-[#00aa55]' : 'bg-[#94a3b8]'}`} />
            Agents Connected: {blockchainMetrics.connectedAgents}
          </span>
        </div>
      </header>

      {/* Tab Bar */}
      <div className="bg-white border-b border-[#cccccc] flex items-center justify-between shrink-0">
        <div className="flex">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-2 px-5 py-3 text-[10px] tracking-widest uppercase border-r border-[#cccccc] transition ${activeTab === tab.key ? 'bg-[#0d1b3e] text-white' : 'bg-white text-[#555] hover:bg-[#f0f0f0]'}`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="flex">
          <button onClick={onLogout} className="flex items-center gap-2 px-6 py-3 text-[10px] tracking-widest text-[#c0392b] hover:bg-red-50 border-l border-[#cccccc] uppercase transition">
            Logout
          </button>
        </div>
      </div>

      <main className="flex-1 p-4 flex flex-col gap-4 overflow-auto">
      {/* ── Analytics Tab ── */}
      {activeTab === 'analytics' && (
        <ThreatAnalyticsTab data={threatHistory} arpFloodLimit={policyConfig.arpFloodLimit} />
      )}

      {/* ── SOP Tab ── */}
      {activeTab === 'sop' && <SopTab />}

      {/* ── Dashboard Tab ── */}
      {activeTab === 'dashboard' && <>

        {/* Agent Status Grid */}
        <section className="shrink-0 border border-[#cccccc] bg-white flex flex-col" style={{ minHeight: 200 }}>
          <div className="bg-[#f5f5f5] border-b border-[#cccccc] p-3 px-4 font-bold text-sm tracking-widest text-[#0F172A] flex items-center gap-2 shrink-0">
            Agent Status Overview
          </div>
          <div className="overflow-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead className="bg-[#F8FAFC] border-b border-[#e2e8f0] sticky top-0 z-10 font-bold uppercase tracking-widest text-xs">
                <tr>
                  <th className="p-3 border-r border-[#e2e8f0] text-[#0F172A]">ID</th>
                  <th className="p-3 border-r border-[#e2e8f0] text-[#0F172A]">Name</th>
                  <th className="p-3 border-r border-[#e2e8f0] text-[#0F172A]">IP Address</th>
                  <th className="p-3 border-r border-[#e2e8f0] text-[#0F172A]">MAC Address</th>
                  <th className="p-3 border-r border-[#e2e8f0] text-[#0F172A]">CPU / RAM</th>
                  <th className="p-3 text-[#0F172A]">Status</th>
                </tr>
              </thead>
              <tbody>
                {agents.map(agent => (
                  <tr key={agent.id} className="border-b border-[#e2e8f0] hover:bg-slate-50 transition">
                    <td className="p-3 border-r border-[#e2e8f0] font-['JetBrains_Mono',_monospace] font-bold opacity-60">{agent.id}</td>
                    <td className="p-3 border-r border-[#e2e8f0] font-bold uppercase tracking-tight">{agent.name}</td>
                    <td className="p-3 border-r border-[#e2e8f0] font-['JetBrains_Mono',_monospace]">{agent.ip}</td>
                    <td className="p-3 border-r border-[#e2e8f0] font-['JetBrains_Mono',_monospace]">{agent.mac}</td>
                    <td className="p-3 border-r border-[#e2e8f0]">
                      {agent.state === 'UNPROTECTED' ? (
                        <div className="text-[#94A3B8] font-bold text-center">-</div>
                      ) : (
                        <div className="flex flex-col gap-1 w-36">
                          <div className="flex justify-between text-[9px] font-bold uppercase">
                            <span>CPU</span>
                            <span className={`font-['JetBrains_Mono',_monospace] ${agent.cpu > 70 ? 'text-[#DC2626]' : 'text-[#0F172A]'}`}>{(agent.cpu ?? 0).toFixed(5)}%</span>
                          </div>
                          <div className="h-1.5 border border-[#e2e8f0] bg-white">
                            <div className={`h-full transition-all duration-500 ${agent.cpu > 70 ? 'bg-[#DC2626]' : 'bg-[#1E3A8A]'}`} style={{ width: `${agent.cpu}%` }} />
                          </div>
                          <div className="flex justify-between text-[9px] font-bold uppercase">
                            <span>RAM</span>
                            <span className="font-['JetBrains_Mono',_monospace] text-[#0F172A]">{agent.ramMb != null ? `${agent.ramMb.toFixed(1)} MB` : '—'}</span>
                          </div>
                          <div className="h-1.5 border border-[#e2e8f0] bg-white">
                            <div className="h-full bg-[#16A34A] transition-all duration-500" style={{ width: `${agent.ramProcessPercent ?? 0}%` }} />
                          </div>
                        </div>
                      )}
                    </td>
                    <td className={`p-3 font-black uppercase tracking-widest w-64 ${agent.state === 'PROTECTED' ? 'text-[#16A34A] bg-[#F1F5F9]' : ''} ${agent.state === 'DETECTING' ? 'text-white bg-[#DC2626] animate-pulse' : ''} ${agent.state === 'SYNCING' ? 'bg-[#F1F5F9]' : ''} ${agent.state === 'UNPROTECTED' ? 'text-[#94A3B8] bg-[#F8FAFC]' : ''}`}>
                      {agent.state === 'PROTECTED' && 'PROTECTED'}
                      {agent.state === 'UNPROTECTED' && 'UNPROTECTED'}
                      {agent.state === 'DETECTING' && <div className="flex items-center gap-2">ATTACK DETECTED</div>}
                      {agent.state === 'SYNCING' && (
                        <div>
                          <div className="flex justify-between text-[10px] text-[#0F172A] mb-1"><span>BAYANIHAN SYNCING</span><span className="font-['JetBrains_Mono',_monospace]">{agent.syncProgress}%</span></div>
                          <div className="w-full h-3 border border-[#e2e8f0] bg-white p-0.5">
                              <div className="h-full bg-[#1a73e8] transition-all duration-300" style={{ width: `${agent.syncProgress}%` }} />
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

        {/* Live Intelligence Stream + Network Blacklist, side by side. The stream
            was a full-width, mostly-empty band; the blacklist is the evidence
            that intelligence actually propagated between agents. */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 shrink-0 items-stretch" style={{ height: 240 }}>
        <section className="border border-[#cccccc] bg-white flex flex-col min-h-0">
          <div className="bg-[#f5f5f5] border-b border-[#cccccc] p-3 px-4 font-bold text-sm tracking-widest text-[#0F172A] flex justify-between items-center shrink-0">
            <span>Live Intelligence Stream (Socket.io)</span>
          </div>
          <div ref={logsContainerRef} className="flex-1 min-h-0 overflow-y-auto p-4 font-['JetBrains_Mono',_monospace] text-sm bg-white text-slate-800 flex flex-col gap-2">
            {logs.map(log => (
              <div key={log.id} className="border-b border-slate-200 pb-2">
                <span className="text-slate-500 mr-2">[{log.timestamp}]</span>
                <span className={`${log.message.startsWith('ALERT') ? 'text-[#DC2626] font-bold' : ''} ${log.message.startsWith('ADMIN') ? 'text-[#1E3A8A] font-bold' : ''} ${log.message.startsWith('POLICY') ? 'text-[#7C3AED] font-bold' : ''}`}>
                  {log.message}
                </span>
              </div>
            ))}
          </div>
        </section>

        <section className="border border-[#cccccc] bg-white flex flex-col min-h-0">
          <div className="bg-[#f5f5f5] border-b border-[#cccccc] p-3 px-4 font-bold text-sm tracking-widest flex items-center gap-2 text-[#0F172A] shrink-0">
            Relay Telemetry
          </div>
          <div className="flex-1 min-h-0 p-5 flex flex-col justify-center">
            <div className="flex gap-6">
              <div className="flex-1 flex flex-col gap-2">
                <div className="flex justify-between text-sm font-bold uppercase"><span>Relay Node CPU</span><span className="font-['JetBrains_Mono',_monospace]">{(telemetry.cpu ?? 0).toFixed(5)}%</span></div>
                <div className="w-full h-8 border border-[#e2e8f0] p-1 bg-white">
                  <div className="h-full bg-[#1a73e8] transition-all duration-500" style={{ width: `${telemetry.cpu}%` }} />
                </div>
              </div>
              <div className="flex-1 flex flex-col gap-2">
                <div className="flex justify-between text-sm font-bold uppercase"><span>Relay Node RAM</span><span className="font-['JetBrains_Mono',_monospace]">{(telemetry.ramMb / 1024).toFixed(1)} / {(telemetry.ramTotalMb / 1024).toFixed(1)} GB</span></div>
                <div className="w-full h-8 border border-[#e2e8f0] p-1 bg-white">
                  <div className="h-full bg-[#1a73e8] transition-all duration-500" style={{ width: `${telemetry.ram}%` }} />
                </div>
              </div>
            </div>
          </div>
        </section>
        </div>

        {/* Bottom row: Blockchain Ledger + Network Blacklist */}
        <section className="grid grid-cols-2 gap-4 shrink-0 items-stretch" style={{ height: 400 }}>

          {/* Blockchain Ledger + Metrics */}
          <div className="border border-[#cccccc] bg-white flex flex-col min-h-0">
            <div className="bg-[#f5f5f5] border-b border-[#cccccc] p-3 px-4 font-bold text-sm tracking-widest flex items-center gap-2 text-[#0F172A] shrink-0">
              Blockchain Ledger (MultiChain)
              <button
                onClick={() => exportCSV(ledger)}
                className="ml-auto flex items-center gap-1 px-3 py-1 border border-[#e2e8f0] text-[10px] font-bold uppercase tracking-widest hover:bg-[#1a73e8] hover:text-white hover:border-[#1a73e8] transition"
              >
                Export CSV
              </button>
            </div>

            {/* Blockchain metrics strip */}
            <div className="grid grid-cols-4 border-b border-[#e2e8f0] font-['JetBrains_Mono',_monospace]">
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

            <div ref={ledgerContainerRef} className="flex-1 min-h-0 overflow-auto">
              <table className="w-full text-left border-collapse font-['JetBrains_Mono',_monospace] text-sm">
                <thead className="bg-[#F8FAFC] border-b border-[#e2e8f0] sticky top-0 z-10">
                  <tr>
                    <th className="p-3 border-r border-[#e2e8f0] font-bold text-[#0F172A]">BlockChain ID</th>
                    <th className="p-3 border-r border-[#e2e8f0] font-bold text-[#0F172A]">Timestamp</th>
                    <th className="p-3 border-r border-[#e2e8f0] font-bold text-[#0F172A]">Source MAC Hash</th>
                    <th className="p-3 font-bold text-[#0F172A]">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {ledger.map((row, i) => (
                    <tr key={row.blockId} className="border-b border-[#e2e8f0] hover:bg-slate-50 transition">
                      <td className="p-3 border-r border-[#e2e8f0]">{row.blockId}</td>
                      <td className="p-3 border-r border-[#e2e8f0]">{row.timestamp}</td>
                      <td className="p-3 border-r border-[#e2e8f0] font-bold">{row.macHash}</td>
                      <td className="p-3 text-[#16A34A] font-bold">{row.score}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Network Blacklist — the shared intelligence of the Bayanihan layer */}
          <div className="border border-[#cccccc] bg-white flex flex-col min-h-0">
          <div className="bg-[#f5f5f5] border-b border-[#cccccc] p-3 px-4 font-bold text-sm tracking-widest text-[#0F172A] flex justify-between items-center shrink-0">
            <span>Network Blacklist (Bayanihan)</span>
            <span className="text-[10px] text-[#64748b] font-['JetBrains_Mono',_monospace]">
              {blacklist.length} SHARED TO {blockchainMetrics.connectedAgents} AGENT{blockchainMetrics.connectedAgents === 1 ? '' : 'S'}
            </span>
          </div>
          <div className="flex-1 min-h-0 overflow-y-auto">
            {blacklist.length === 0 ? (
              <p className="p-4 text-[#64748b] text-xs">
                No shared threats yet. A MAC appears here as soon as any agent reports it,
                and is replayed to every agent that connects afterwards.
              </p>
            ) : (
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-[#f5f5f5]">
                  <tr className="text-[#475569] text-[10px] uppercase tracking-widest">
                    <th className="text-left p-3 border-r border-[#e2e8f0]">Source MAC</th>
                    <th className="text-left p-3 border-r border-[#e2e8f0]">First Seen</th>
                    <th className="text-left p-3 border-r border-[#e2e8f0]">Reported By</th>
                    <th className="text-left p-3">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {blacklist.map(b => (
                    <tr key={b.mac} className="border-t border-[#e2e8f0]">
                      <td className="p-3 border-r border-[#e2e8f0] font-bold font-['JetBrains_Mono',_monospace]">{b.mac}</td>
                      <td className="p-3 border-r border-[#e2e8f0] font-['JetBrains_Mono',_monospace]">{b.firstSeen}</td>
                      <td className="p-3 border-r border-[#e2e8f0]">{b.reportedBy}</td>
                      <td className="p-3 font-['JetBrains_Mono',_monospace] text-[#1a73e8]">{b.confidence}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          </div>
        </section>

      </>}
      </main>
    </div>
  );
}