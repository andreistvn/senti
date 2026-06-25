import React, { useState } from 'react';
import { Radio, Sliders, Zap, CheckCircle, Cpu, Server } from 'lucide-react';

export interface PolicyConfig {
  mlThreshold: number;
  arpFloodLimit: number;
  autoBlacklist: boolean;
  syncInterval: number;
  logRetentionDays: number;
}

export interface AgentHealth {
  id: string;
  name: string;
  ip: string;
  mac: string;
  cpu: number;
  ram: number;
  connectedSince: string;
  packetsProcessed: number;
  state: string;
}

interface Props {
  config: PolicyConfig;
  agents: AgentHealth[];
  onBroadcast: (config: PolicyConfig, changes: string[]) => void;
}

function SliderRow({
  label, desc, value, min, max, step, unit, onChange,
}: {
  label: string; desc: string; value: number; min: number; max: number;
  step: number; unit: string; onChange: (v: number) => void;
}) {
  return (
    <div className="border-b border-[#E2E8F0] pb-4">
      <div className="flex justify-between items-baseline mb-1">
        <span className="text-xs font-bold uppercase tracking-widest text-[#0F172A]">{label}</span>
        <span className="font-['JetBrains_Mono',_monospace] text-lg font-bold text-[#1E3A8A]">{value}{unit}</span>
      </div>
      <p className="text-[#94A3B8] text-[10px] uppercase tracking-wider mb-3">{desc}</p>
      <input
        type="range"
        min={min} max={max} step={step} value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full h-2 appearance-none bg-[#E2E8F0] outline-none cursor-pointer"
        style={{ accentColor: '#1E3A8A' }}
      />
      <div className="flex justify-between text-[9px] font-['JetBrains_Mono',_monospace] text-[#94A3B8] mt-1">
        <span>{min}{unit}</span>
        <span>{max}{unit}</span>
      </div>
    </div>
  );
}

function ToggleRow({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex justify-between items-center border-b border-[#E2E8F0] pb-3">
      <span className="text-[#64748B] uppercase tracking-widest text-xs">{label}</span>
      <button
        onClick={() => onChange(!value)}
        className={`px-4 py-1.5 text-xs font-bold uppercase tracking-widest border-2 transition-none ${value ? 'bg-[#1E3A8A] border-[#1E3A8A] text-white' : 'bg-white border-[#94A3B8] text-[#94A3B8]'}`}
      >
        {value ? 'ENABLED' : 'DISABLED'}
      </button>
    </div>
  );
}

export default function PolicyTab({ config, agents, onBroadcast }: Props) {
  const [local, setLocal] = useState<PolicyConfig>({ ...config });
  const [lastBroadcast, setLastBroadcast] = useState<string | null>(null);
  const [broadcastPending, setBroadcastPending] = useState(false);

  const changed: string[] = [];
  if (local.mlThreshold    !== config.mlThreshold)    changed.push(`ML Threshold: ${config.mlThreshold} → ${local.mlThreshold}`);
  if (local.arpFloodLimit  !== config.arpFloodLimit)  changed.push(`ARP Flood Limit: ${config.arpFloodLimit} → ${local.arpFloodLimit} PPS`);
  if (local.autoBlacklist  !== config.autoBlacklist)  changed.push(`Auto-Blacklist: ${config.autoBlacklist ? 'ON' : 'OFF'} → ${local.autoBlacklist ? 'ON' : 'OFF'}`);
  if (local.syncInterval   !== config.syncInterval)   changed.push(`Sync Interval: ${config.syncInterval} → ${local.syncInterval} ms`);
  if (local.logRetentionDays !== config.logRetentionDays) changed.push(`Log Retention: ${config.logRetentionDays} → ${local.logRetentionDays} days`);

  const handleBroadcast = () => {
    if (changed.length === 0) return;
    setBroadcastPending(true);
    setTimeout(() => {
      onBroadcast(local, changed);
      const now = new Date();
      setLastBroadcast(`${now.getHours().toString().padStart(2,'0')}:${now.getMinutes().toString().padStart(2,'0')}:${now.getSeconds().toString().padStart(2,'0')}`);
      setBroadcastPending(false);
    }, 800);
  };

  const set = (key: keyof PolicyConfig) => (v: number | boolean) =>
    setLocal(p => ({ ...p, [key]: v }));

  return (
    <div className="flex flex-col gap-4">

      <div className="grid grid-cols-2 gap-4">

        {/* Policy configurator */}
        <section className="border border-[#cccccc] bg-white flex flex-col">
          <div className="bg-[#f5f5f5] border-b border-[#cccccc] p-3 px-4 font-bold text-sm tracking-widest flex items-center gap-2 text-[#0F172A] shrink-0">
            <Sliders className="w-5 h-5" />
            Global Policy Configurator
          </div>
          <div className="flex-1 p-5 flex flex-col gap-4 font-['JetBrains_Mono',_monospace] text-sm">
            <SliderRow
              label="ML Confidence Threshold"
              desc="Minimum model confidence to flag a packet as malicious"
              value={local.mlThreshold}
              min={0.10} max={0.99} step={0.01} unit=""
              onChange={set('mlThreshold') as (v: number) => void}
            />
            <SliderRow
              label="ARP Flood Alert Limit"
              desc="Packets-per-second threshold that triggers a critical alert"
              value={local.arpFloodLimit}
              min={100} max={5000} step={50} unit=" PPS"
              onChange={set('arpFloodLimit') as (v: number) => void}
            />
            <SliderRow
              label="Sync Interval"
              desc="Frequency of Bayanihan Sync broadcasts to all agents"
              value={local.syncInterval}
              min={1000} max={30000} step={500} unit=" ms"
              onChange={set('syncInterval') as (v: number) => void}
            />
            <SliderRow
              label="Log Retention"
              desc="Number of days to retain raw intelligence stream entries"
              value={local.logRetentionDays}
              min={7} max={365} step={1} unit=" days"
              onChange={set('logRetentionDays') as (v: number) => void}
            />
            <ToggleRow label="Auto-Blacklist on Threat" value={local.autoBlacklist} onChange={set('autoBlacklist') as (v: boolean) => void} />
          </div>
          <div className="border-t border-[#e2e8f0] p-4 flex items-center gap-4">
            {changed.length > 0 ? (
              <div className="flex-1 text-[10px] text-[#DC2626] font-bold uppercase tracking-widest">
                {changed.length} unsaved change{changed.length > 1 ? 's' : ''}
              </div>
            ) : (
              <div className="flex-1 text-[10px] text-[#94A3B8] uppercase tracking-widest">No pending changes</div>
            )}
            <button
              onClick={handleBroadcast}
              disabled={changed.length === 0 || broadcastPending}
              className={`flex items-center gap-2 px-5 py-3 text-xs font-bold uppercase tracking-widest border transition ${changed.length > 0 && !broadcastPending ? 'bg-[#0d1b3e] border-[#0d1b3e] text-white hover:bg-[#102245]' : 'bg-[#f9fafb] border-[#E2E8F0] text-[#94A3B8] cursor-not-allowed'}`}
            >
              {broadcastPending ? (
                <><Radio className="w-4 h-4 animate-ping" />Broadcasting...</>
              ) : (
                <><Zap className="w-4 h-4" />Broadcast to All Agents</>
              )}
            </button>
          </div>
          {lastBroadcast && (
            <div className="border-t-2 border-[#16A34A] bg-[#F0FDF4] p-3 flex items-center gap-2 text-[#16A34A] text-xs font-bold uppercase tracking-widest">
              <CheckCircle className="w-4 h-4" />Policy broadcast confirmed at {lastBroadcast}
            </div>
          )}
        </section>

        {/* Active Node Topology & Health Map */}
        <section className="border border-[#cccccc] bg-white flex flex-col">
          <div className="bg-[#f5f5f5] border-b border-[#cccccc] p-3 px-4 font-bold text-sm tracking-widest flex items-center gap-2 text-[#0F172A] shrink-0">
            <Server className="w-5 h-5" />
            Active Node Topology & Health Map
            <span className="ml-auto font-['JetBrains_Mono',_monospace] text-[#16A34A] text-xs">
              {agents.length} CONNECTED
            </span>
          </div>
          <div className="flex-1 overflow-auto p-4 flex flex-col gap-3">
            {agents.map(agent => {
              const cpuHigh = agent.cpu > 70;
              const ramHigh = agent.ram > 75;
              return (
                <div key={agent.id} className={`border p-4 ${cpuHigh ? 'border-[#DC2626]' : 'border-[#E2E8F0]'} bg-[#F8FAFC]`}>
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <div className="font-bold uppercase tracking-wide text-sm text-[#0F172A]">{agent.name}</div>
                      <div className="font-['JetBrains_Mono',_monospace] text-[10px] text-[#94A3B8]">{agent.ip} · {agent.mac}</div>
                    </div>
                    <div className={`px-2 py-0.5 text-[9px] font-bold uppercase tracking-widest border ${agent.state === 'PROTECTED' ? 'bg-[#F0FDF4] border-[#16A34A] text-[#16A34A]' : 'bg-[#FEF2F2] border-[#DC2626] text-[#DC2626]'}`}>
                      {agent.state}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <div className="flex justify-between text-[9px] font-bold uppercase mb-1">
                        <span className="flex items-center gap-1"><Cpu className="w-3 h-3" />CPU</span>
                        <span className={`font-['JetBrains_Mono',_monospace] ${cpuHigh ? 'text-[#DC2626]' : 'text-[#0F172A]'}`}>{agent.cpu}%</span>
                      </div>
                      <div className="h-2 border border-[#e2e8f0] bg-white">
                        <div className={`h-full transition-all duration-500 ${cpuHigh ? 'bg-[#DC2626]' : 'bg-[#1E3A8A]'}`} style={{ width: `${agent.cpu}%` }} />
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between text-[9px] font-bold uppercase mb-1">
                        <span>RAM</span>
                        <span className={`font-['JetBrains_Mono',_monospace] ${ramHigh ? 'text-[#DC2626]' : 'text-[#0F172A]'}`}>{agent.ram}%</span>
                      </div>
                      <div className="h-2 border border-[#e2e8f0] bg-white">
                        <div className={`h-full transition-all duration-500 ${ramHigh ? 'bg-[#DC2626]' : 'bg-[#16A34A]'}`} style={{ width: `${agent.ram}%` }} />
                      </div>
                    </div>
                  </div>
                  <div className="mt-2 flex justify-between text-[9px] font-['JetBrains_Mono',_monospace] text-[#94A3B8]">
                    <span>Connected since {agent.connectedSince}</span>
                    <span>{agent.packetsProcessed.toLocaleString()} pkts</span>
                  </div>
                  {cpuHigh && (
                    <div className="mt-2 text-[9px] font-bold uppercase tracking-widest text-[#DC2626] flex items-center gap-1">
                      ⚠ CPU BOTTLENECK — HIGH LOCALIZED TRAFFIC
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>

      </div>
    </div>
  );
}