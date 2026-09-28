import React from 'react';
import {
  Shield, Radio, Clock, Activity, Database,
  TrendingUp, Users, Award
} from 'lucide-react';
import { LineChart, Line, ResponsiveContainer } from 'recharts';
import { Power } from 'lucide-react';
import { useDashboardState } from '../dashboard/useDashboardState';

export default function Dashboard() {
  const {
    cpuData,
    lastUpdate,
    eProtected,
    eInspected,
    eDropped,
    ePassed,
    eMemory,
    eMemoryMb,
    eSigContrib,
    eUsersProtected,
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
            <PanelHeader icon={<Database className="w-4 h-4 text-[#1a4fd6]" strokeWidth={2} />} title="System RAM Usage" />
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
                <p className="text-[#888] text-[10px] tracking-wider mt-2">Total Machine Memory</p>
                <p className="text-[#111] text-[11px] font-bold tracking-wider mt-1">
                  SentiNet: {typeof eMemoryMb === 'number' ? eMemoryMb.toFixed(1) : eMemoryMb} MB
                </p>
              </div>
              <p className="text-[#888] text-[10px] tracking-wider mt-2">Total Machine Memory</p>
            </div>
          </div>

          <div className="bg-white border border-[#cccccc]">
            <PanelHeader icon={<TrendingUp className="w-4 h-4 text-[#1a4fd6]" strokeWidth={2} />} title="Traffic Throughput (PPS)" />
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