import React from 'react';
import ScrollingLine from './ScrollingLine';
import { useDashboardState } from '../dashboard/useDashboardState';

export default function Dashboard() {
  const {
    cpuData,
    cpuIntervalMs,
    lastUpdate,
    eProtected,
    eRelayOnline,
    eNetwork,
    eInspected,
    eDropped,
    ePassed,
    eMemory,
    eMemoryMb,
    eIdentity,
    eBlacklist,
    eSigContrib,
    eReportsPending,
    eLastThreat,
    eLogs,
    detectionLogsContainerRef,
    live,
    tray,
  } = useDashboardState();

  return (
    <div className="min-h-screen bg-[#e8eaed] flex flex-col">

      {/* Header */}
      <header className="bg-[#0d1b3e] border-b-2 border-[#c0392b] px-6 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-white tracking-widest text-sm font-bold uppercase">SentiNet Agent Dashboard</span>
        </div>
        <div className="flex items-center gap-6 text-xs">
          <span className="text-[#8899bb] tracking-wider">
            {eIdentity.ip || '—'} / {eIdentity.mac || '—'}
          </span>
          {!live && (
            <span className="flex items-center gap-2 text-[#f59e0b]" title="Tray daemon not detected — showing simulated data">
              <span className="w-2 h-2 rounded-full bg-[#f59e0b] animate-pulse inline-block" />
              MOCK MODE
            </span>
          )}
        </div>
      </header>

      <div className="flex-1 p-5 space-y-4 overflow-auto max-w-[1800px] mx-auto w-full">

        {/* Row 1: Status Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white border border-[#cccccc]">
            <PanelHeader title="Protection Status" />
            <div className="p-5">
              <div
                className="inline-flex items-center gap-2 px-5 py-2.5 mb-3"
                style={{ background: eProtected ? '#00aa55' : '#3a5070' }}
              >
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
                  {eProtected ? 'TURN OFF PROTECTION' : 'TURN ON PROTECTION'}
                </button>
              )}
            </div>
          </div>

          <div className="bg-white border border-[#cccccc]">
            <PanelHeader title="Relay Connection" />
            <div className="p-5">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-2.5 h-2.5 shrink-0" style={{ background: eRelayOnline ? '#00aa55' : '#3a5070' }} />
                <span className="text-[#111] text-sm tracking-widest font-bold">
                  RELAY: {eRelayOnline ? 'ONLINE' : 'OFFLINE'}
                </span>
              </div>
              <p className="text-[#888] text-[10px] tracking-wider">Network: {eNetwork || '—'}</p>
            </div>
          </div>

          <div className="bg-white border border-[#cccccc]">
            <PanelHeader title="Last Detected Threat" />
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
            <PanelHeader title="CPU Load (Tier-1 Efficiency)" />
            <div className="p-5">
              <ScrollingLine values={cpuData.map(d => d.usage)} intervalMs={cpuIntervalMs} />
              <div className="flex items-baseline gap-2 mt-2">
                <span className="text-[#111] text-xl font-bold tracking-widest">{cpuData[cpuData.length - 1].usage.toFixed(5)}%</span>
                <span className="text-[#00aa55] text-[10px] tracking-widest">LOW IMPACT</span>
              </div>
            </div>
          </div>

          <div className="bg-white border border-[#cccccc]">
            <PanelHeader title="System RAM Usage" />
            <div className="p-5 flex flex-col items-center">
              <div className="relative w-28 h-28">
                <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                  <circle cx="50" cy="50" r="42" stroke="#e0e0e0" strokeWidth="10" fill="none" />
                  <circle cx="50" cy="50" r="42" stroke="#1a4fd6" strokeWidth="10" fill="none"
                    strokeDasharray={`${2 * Math.PI * 42}`}
                    strokeDashoffset={`${2 * Math.PI * 42 * (1 - eMemory / 100)}`}
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-[#111] text-base font-bold">{typeof eMemory === 'number' ? eMemory.toFixed(1) : eMemory}%</span>
                </div>
              </div>
              <p className="text-[#888] text-[10px] tracking-wider mt-2">Total Machine Memory</p>
              <p className="text-[#111] text-[11px] font-bold tracking-wider mt-1">
                SentiNet: {typeof eMemoryMb === 'number' ? eMemoryMb.toFixed(1) : eMemoryMb} MB
              </p>
            </div>
          </div>

          <div className="bg-white border border-[#cccccc]">
            <PanelHeader title="Traffic Throughput (PPS)" />
            <div className="p-5 space-y-3">
              {[
                { label: 'INSPECTED', value: eInspected.toLocaleString(), pct: 100, color: '#1a4fd6', textColor: '#111', hideBar: true },
                { label: 'DROPPED',   value: eDropped.toLocaleString(),   pct: eInspected > 0 ? (eDropped / eInspected) * 100 : 0, color: '#c0392b', textColor: '#c0392b' },
                { label: 'PASSED',    value: ePassed.toLocaleString(),    pct: eInspected > 0 ? (ePassed / eInspected) * 100 : 0, color: '#00aa55', textColor: '#00aa55' },
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

        {/* Row 3: Detection Log + Blacklist */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-stretch" style={{ minHeight: 320 }}>
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

          <div className="flex flex-col">
            {/* Tier-1 Blacklist — the visible evidence of the Bayanihan layer.
                Entries marked "From Relay" were learned from another agent, so on
                a node that was never attacked every row reads relay. That is the
                collaborative defense shown directly, rather than inferred from a
                dropped-packet counter. */}
            <div className="bg-white border border-[#cccccc] flex flex-col flex-1 min-h-0">
              <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-[#cccccc] bg-[#0d1b3e] shrink-0">
                <div className="flex items-center gap-2">
                  <span className="text-white text-[10px] tracking-widest uppercase font-bold">Tier-1 Blacklist</span>
                </div>
                <span className="text-[#8899bb] text-[10px] tracking-widest">
                  {eBlacklist.length} BLOCKED &middot; {eSigContrib} SHARED
                  {eReportsPending > 0 && (
                    <span className="text-[#f59e0b]"> &middot; {eReportsPending} PENDING</span>
                  )}
                </span>
              </div>

              {eBlacklist.length === 0 ? (
                <div className="p-4">
                  <p className="text-[#888] text-[10px] tracking-wider">
                    No blocked MACs yet. Entries appear when this node detects a threat,
                    or when the relay shares one found by another agent.
                  </p>
                </div>
              ) : (
                <div className="flex-1 overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-[#f5f5f5]">
                      <tr className="text-[#555] text-[9px] tracking-widest uppercase">
                        <th className="text-left p-2 font-bold">Source MAC</th>
                        <th className="text-left p-2 font-bold">Added</th>
                        <th className="text-left p-2 font-bold">Origin</th>
                      </tr>
                    </thead>
                    <tbody>
                      {eBlacklist.map(b => (
                        <tr key={b.mac} className="border-t border-[#eee]">
                          <td className="p-2 font-['JetBrains_Mono',_monospace] text-[#111]">{b.mac}</td>
                          <td className="p-2 text-[#555] font-['JetBrains_Mono',_monospace]">{b.addedAt}</td>
                          <td className="p-2">
                            <span className={`text-[9px] tracking-widest uppercase font-bold px-1.5 py-0.5 ${
                              b.origin === 'relay' ? 'bg-[#1a4fd6] text-white' : 'bg-[#e0e0e0] text-[#555]'
                            }`}>
                              {b.origin === 'relay' ? 'From Relay' : 'Local'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function PanelHeader({ title }: { title: string }) {
  return (
    <div className="flex items-center gap-2 px-4 py-3 border-b border-[#cccccc] bg-[#f5f5f5]">
      <span className="text-[#0d1b3e] text-[10px] tracking-widest uppercase font-bold">{title}</span>
    </div>
  );
}
