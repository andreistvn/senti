import React, { useEffect, useMemo, useState } from 'react';
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Legend,
} from 'recharts';
import { getTrafficAnalytics, type TrafficAnalytics } from '../lib/adminApi';

// Every figure on this tab comes from the agents' own ARP packet counts, sent
// with their telemetry (see admin-backend/analytics.py). "Blocked" is a Tier-1
// hit: the sender was on the blacklist. A Linux agent's kernel also drops it; a
// Windows or macOS agent can only count it, which the agent table says.

const POLL_MS = 2000;
// One colour per agent line, after the blue total and red blocked series.
const AGENT_COLOURS = ['#0EA5E9', '#16A34A', '#F59E0B', '#7C3AED', '#DB2777', '#0F766E'];

const AXIS_TICK = { fontSize: 9, fontFamily: 'JetBrains Mono', fill: '#94A3B8' };
const LEGEND_STYLE = { fontSize: 10, fontFamily: 'JetBrains Mono', textTransform: 'uppercase' as const, letterSpacing: '0.1em' };

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#0F172A] border-2 border-[#334155] p-3 font-['JetBrains_Mono',_monospace] text-xs">
      <p className="text-[#94A3B8] mb-1">{label}</p>
      {payload.map((p: any) => (
        <p key={p.name} style={{ color: p.color }}>{p.name}: {Number(p.value).toLocaleString()}</p>
      ))}
    </div>
  );
};

function clock(ms: number) {
  const d = new Date(ms);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function Section({ title, note, children, height }: { title: string; note?: string; children: React.ReactNode; height?: number }) {
  return (
    <section className="border border-[#cccccc] bg-white flex flex-col">
      <div className="bg-[#f5f5f5] border-b border-[#cccccc] p-3 px-4 font-bold text-sm tracking-widest flex items-center gap-2 text-[#0F172A] shrink-0">
        {title}
        {note && <span className="ml-auto font-normal text-[10px] text-[#94A3B8] uppercase tracking-widest">{note}</span>}
      </div>
      <div className="p-4" style={height ? { height } : undefined}>{children}</div>
    </section>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <div className="h-full min-h-[80px] flex items-center justify-center text-[10px] uppercase tracking-widest text-[#94A3B8]">
      {text}
    </div>
  );
}

export default function ThreatAnalyticsTab() {
  const [data, setData] = useState<TrafficAnalytics | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [period, setPeriod] = useState<'daily' | 'weekly' | 'monthly'>('daily');

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const next = await getTrafficAnalytics();
      if (!alive) return;
      setData(next);
      setLoaded(true);
    };
    void load();
    const poll = setInterval(load, POLL_MS);
    return () => {
      alive = false;
      clearInterval(poll);
    };
  }, []);

  const agents = data?.agents ?? [];
  const session = data?.session;

  // Recharts wants one flat row per point; agent MACs become stable keys.
  const agentKeys = useMemo(
    () => agents.map((a, i) => ({ ...a, key: `agent_${i}`, colour: AGENT_COLOURS[i % AGENT_COLOURS.length] })),
    [agents],
  );
  const liveRows = useMemo(
    () => (data?.live ?? []).map(point => {
      // "Normal" is everything the agents saw that was NOT blocked. Showing it
      // explicitly keeps an operator from reading a busy-but-healthy network as
      // an attack (the panel's anti-false-alarm ask).
      const normal = Math.max(0, point.pps - point.blocked);
      const row: Record<string, number | string> = { time: clock(point.t), pps: point.pps, normal, blocked: point.blocked };
      agentKeys.forEach(a => { row[a.key] = point.agents[a.mac] ?? 0; });
      return row;
    }),
    [data, agentKeys],
  );

  const periodRows = data ? data[period] : [];
  const periodLabel = { daily: 'per hour, last 24 hours', weekly: 'per day, last 7 days', monthly: 'per day, last 30 days' }[period];

  const normalNow = session
    ? Math.max(0, (session.currentPps ?? 0) - (session.currentBlockedPps ?? 0))
    : undefined;

  const statCards = [
    { label: 'ARP Traffic Now', value: session?.currentPps, unit: 'packets / s, all agents' },
    { label: 'Normal Now', value: normalNow, unit: 'packets / s, not blocked' },
    { label: 'Blocked Now', value: session?.currentBlockedPps, unit: 'blocks / s, all agents' },
    { label: 'Peak Traffic', value: session?.peakPps, unit: 'packets / s, since relay start' },
    { label: 'Average Traffic', value: session?.avgPps, unit: 'packets / s, since relay start' },
  ];

  if (loaded && !data) {
    return (
      <section className="border border-[#cccccc] bg-white p-6">
        <Empty text="Relay unreachable — no analytics available" />
      </section>
    );
  }

  return (
    <div className="flex flex-col gap-4">

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {statCards.map(s => (
          <div key={s.label} className="border border-[#e2e8f0] bg-white p-4 flex flex-col gap-1">
            <span className="text-[#94A3B8] text-[10px] uppercase tracking-widest">{s.label}</span>
            <span className="font-['JetBrains_Mono',_monospace] text-3xl font-bold text-[#0F172A]">
              {s.value == null ? '—' : s.value.toLocaleString()}
            </span>
            <span className="text-[#94A3B8] text-[10px] uppercase tracking-widest">{s.unit}</span>
          </div>
        ))}
      </div>

      <Section title="Live Network Traffic — ARP Packets Per Second" note="last 5 minutes" height={280}>
        {liveRows.length === 0 ? (
          <Empty text={agents.length ? 'Waiting for agent reports' : 'No agents connected'} />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={liveRows} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="gradPPS" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#1E3A8A" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#1E3A8A" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="gradBlocked" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#DC2626" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#DC2626" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="gradNormal" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#16A34A" stopOpacity={0.28} />
                  <stop offset="95%" stopColor="#16A34A" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
              <XAxis dataKey="time" tick={AXIS_TICK} interval="preserveStartEnd" minTickGap={40} />
              <YAxis tick={AXIS_TICK} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={LEGEND_STYLE} />
              <Area type="monotone" dataKey="pps" stroke="#1E3A8A" strokeWidth={2} fill="url(#gradPPS)" name="All agents" dot={false} isAnimationActive={false} />
              <Area type="monotone" dataKey="normal" stroke="#16A34A" strokeWidth={2} fill="url(#gradNormal)" name="Normal" dot={false} isAnimationActive={false} />
              <Area type="monotone" dataKey="blocked" stroke="#DC2626" strokeWidth={2} fill="url(#gradBlocked)" name="Blocked" dot={false} isAnimationActive={false} />
              {agentKeys.length > 1 && agentKeys.map(a => (
                <Line key={a.key} type="monotone" dataKey={a.key} stroke={a.colour} strokeWidth={1.5}
                  strokeDasharray="4 3" dot={false} name={a.name} isAnimationActive={false} />
              ))}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </Section>

      <Section title="Per-Agent Traffic" note="totals since each agent started">
        {agents.length === 0 ? (
          <Empty text="No agents connected" />
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[9px] uppercase tracking-widest text-[#94A3B8] border-b border-[#e2e8f0]">
                <th className="py-2 pr-3 font-normal">Agent</th>
                <th className="py-2 pr-3 font-normal">MAC</th>
                <th className="py-2 pr-3 font-normal">Blocking</th>
                <th className="py-2 pr-3 font-normal text-right">ARP / s</th>
                <th className="py-2 pr-3 font-normal text-right">Blocked / s</th>
                <th className="py-2 pr-3 font-normal text-right">ARP Packets</th>
                <th className="py-2 font-normal text-right">Blocked</th>
              </tr>
            </thead>
            <tbody className="font-['JetBrains_Mono',_monospace] text-[#0F172A]">
              {agentKeys.map(a => (
                <tr key={a.mac} className="border-b border-[#f1f5f9] last:border-0">
                  <td className="py-2 pr-3 font-bold">
                    <span className="inline-block w-2 h-2 mr-2 align-middle" style={{ background: a.colour }} />
                    {a.name}
                  </td>
                  <td className="py-2 pr-3 text-[#64748B]">{a.mac}</td>
                  <td className="py-2 pr-3">
                    <span className={`text-[9px] uppercase tracking-widest px-1.5 py-0.5 ${a.enforcement === 'kernel' ? 'bg-[#1E3A8A] text-white' : 'bg-[#e2e8f0] text-[#475569]'}`}>
                      {a.enforcement === 'kernel' ? 'Kernel drop' : 'Counted only'}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-right">{a.pps.toLocaleString()}</td>
                  <td className={`py-2 pr-3 text-right ${a.blockedPps > 0 ? 'text-[#DC2626]' : ''}`}>{a.blockedPps.toLocaleString()}</td>
                  <td className="py-2 pr-3 text-right">{a.packets.toLocaleString()}</td>
                  <td className="py-2 text-right">{a.blocked.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      <section className="border border-[#cccccc] bg-white flex flex-col">
        <div className="bg-[#f5f5f5] border-b border-[#cccccc] p-3 px-4 font-bold text-sm tracking-widest flex items-center gap-2 text-[#0F172A] shrink-0">
          ARP Packets — {periodLabel}
          <div className="ml-auto flex items-center gap-2">
            {(['daily', 'weekly', 'monthly'] as const).map(p => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1 text-xs font-bold uppercase tracking-widest ${period === p ? 'bg-[#1E3A8A] text-white' : 'bg-white text-[#0F172A] border'} rounded`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>
        <div className="p-4" style={{ height: 240 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={periodRows} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
              <XAxis dataKey="label" tick={AXIS_TICK} interval="preserveStartEnd" minTickGap={10} />
              <YAxis tick={AXIS_TICK} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={LEGEND_STYLE} />
              <Bar dataKey="packets" name="ARP packets" fill="#1E3A8A" maxBarSize={28} isAnimationActive={false} />
              <Bar dataKey="blocked" name="Blocked" fill="#DC2626" maxBarSize={28} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <Section title="Threat Incidents — Last 24 Hours" note="from agent attack reports" height={220}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data?.incidents ?? []} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
            <XAxis dataKey="label" tick={AXIS_TICK} interval="preserveStartEnd" minTickGap={10} />
            <YAxis tick={AXIS_TICK} allowDecimals={false} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={LEGEND_STYLE} />
            <Bar dataKey="detections" name="New detections (Tier 2)" fill="#1E3A8A" maxBarSize={20} isAnimationActive={false} />
            <Bar dataKey="blocks" name="Still-blocking reports (Tier 1 / 3)" fill="#16A34A" maxBarSize={20} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </Section>

    </div>
  );
}
