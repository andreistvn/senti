import React, { useMemo, useState } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ResponsiveContainer, BarChart, Bar, Legend,
} from 'recharts';
import { TrendingUp, BarChart2, AlertTriangle } from 'lucide-react';

export interface ThreatDataPoint {
  time: string;
  pps: number;
  blocked: number;
}

interface Props {
  data: ThreatDataPoint[];
  arpFloodLimit: number;
}

const HOURLY_DATA = (() => {
  const base = [18,12,8,5,4,3,6,22,45,80,120,135,98,110,145,189,230,310,420,510,480,390,280,190];
  return base.map((v, i) => ({
    hour: `${String(i).padStart(2,'0')}:00`,
    incidents: v + Math.floor(Math.random() * 30),
    blocked: Math.floor((v + Math.random() * 30) * 0.87),
  }));
})();

// Mock generator for showcase/demo when no real `data` is provided.
const generateMockData = (days = 3, intervalMinutes = 5) => {
  const points: ThreatDataPoint[] = [];
  const now = Date.now();
  const total = Math.floor((days * 24 * 60) / intervalMinutes);
  for (let i = total - 1; i >= 0; i--) {
    const t = new Date(now - i * intervalMinutes * 60000);
    // base diurnal pattern + noise
    const hour = t.getUTCHours();
    const base = Math.max(5, Math.round(20 + Math.sin((hour / 24) * Math.PI * 2) * 40));
    const noise = Math.round(Math.random() * 20 - 10);
    points.push({ time: t.toISOString(), pps: Math.max(1, base + noise), blocked: Math.round(Math.max(0, (base + noise) * (0.6 + Math.random() * 0.4))) });
  }
  // inject a few bursts
  const injectBurst = (startOffsetMinutes: number, durationMinutes: number, peak: number) => {
    const start = Date.now() - startOffsetMinutes * 60000;
    for (let m = 0; m < durationMinutes; m += intervalMinutes) {
      const ts = new Date(start + m * 60000).toISOString();
      const idx = points.findIndex(p => p.time === ts);
      if (idx >= 0) {
        points[idx].pps = Math.max(points[idx].pps, Math.round(peak * (0.6 + Math.random() * 0.4)));
        points[idx].blocked = Math.round(points[idx].pps * (0.7 + Math.random() * 0.25));
      }
    }
  };
  injectBurst(60, 30, 300); // 1 hour ago for 30 minutes
  injectBurst(60*24 + 120, 45, 420); // yesterday + 2h
  injectBurst(60*48 + 300, 90, 680); // 2 days ago + 5h
  return points;
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#0F172A] border-2 border-[#334155] p-3 font-['JetBrains_Mono',_monospace] text-xs">
      <p className="text-[#94A3B8] mb-1">{label}</p>
      {payload.map((p: any) => (
        <p key={p.name} style={{ color: p.color }}>{p.name}: {p.value.toLocaleString()}</p>
      ))}
    </div>
  );
};

export default function ThreatAnalyticsTab({ data, arpFloodLimit }: Props) {
  const [useMock, setUseMock] = useState<boolean>(!data || data.length === 0);
  const displayData = useMemo(() => (useMock ? generateMockData(3, 5) : (data && data.length ? data : generateMockData(3, 5))), [data, useMock]);

  const peakPPS    = useMemo(() => Math.max(...displayData.map(d => d.pps)), [displayData]);
  const avgPPS     = useMemo(() => Math.round(displayData.reduce((s, d) => s + d.pps, 0) / Math.max(displayData.length, 1)), [displayData]);
  const currentPPS = displayData[displayData.length - 1]?.pps ?? 0;
  const isOverLimit = currentPPS >= arpFloodLimit;

  const statCards = [
    { label: 'Current ARP PPS',      value: currentPPS, unit: 'pps',      alert: isOverLimit },
    { label: 'Peak PPS (Session)',    value: peakPPS,    unit: 'pps',      alert: peakPPS >= arpFloodLimit },
    { label: 'Avg PPS (Session)',     value: avgPPS,     unit: 'pps',      alert: false },
    { label: 'Alert Threshold',       value: arpFloodLimit, unit: 'pps limit', alert: false },
  ];

  const [period, setPeriod] = useState<'daily'|'weekly'>('daily');

  // Hourly profile (average pps per hour across samples) and weekday profile (total pps per weekday)
  const hourlyProfile = useMemo(() => {
    const buckets = Array.from({ length: 24 }, (_, i) => ({ hour: i, label: String(i).padStart(2, '0') + ':00', pps: 0, count: 0 }));
    displayData.forEach(d => {
      const dt = new Date(d.time);
      if (isNaN(dt.getTime())) return;
      const h = dt.getUTCHours();
      buckets[h].pps += d.pps;
      buckets[h].count += 1;
    });
    return buckets.map(b => ({ hour: b.hour, label: b.label, pps: b.count ? Math.round(b.pps / b.count) : 0 }));
  }, [displayData]);

  const weekdayProfile = useMemo(() => {
    const names = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
    const buckets = names.map((n, i) => ({ day: i, label: n, pps: 0 }));
    displayData.forEach(d => {
      const dt = new Date(d.time);
      if (isNaN(dt.getTime())) return;
      const day = dt.getUTCDay();
      buckets[day].pps += d.pps;
    });
    return buckets.map(b => ({ day: b.day, label: b.label, pps: b.pps }));
  }, [displayData]);

  return (
    <div className="flex flex-col gap-4">

      {/* Stat summary row */}
      <div className="grid grid-cols-4 gap-4">
        {statCards.map(s => (
          <div
            key={s.label}
            className={`border p-4 flex flex-col gap-1 ${s.alert ? 'border-[#DC2626] bg-[#FEF2F2]' : 'border-[#e2e8f0] bg-white'}`}
          >
            <span className="text-[#94A3B8] text-[10px] uppercase tracking-widest">{s.label}</span>
            <span className={`font-['JetBrains_Mono',_monospace] text-3xl font-bold ${s.alert ? 'text-[#DC2626]' : 'text-[#0F172A]'}`}>
              {s.value.toLocaleString()}
            </span>
            <span className="text-[#94A3B8] text-[10px] uppercase tracking-widest">{s.unit}</span>
            {s.alert && (
              <span className="flex items-center gap-1 text-[#DC2626] text-[10px] font-bold uppercase">
                <AlertTriangle className="w-3 h-3" />Exceeds Limit
              </span>
            )}
          </div>
        ))}
      </div>

      {/* Live rolling time-series */}
      <section className="border border-[#cccccc] bg-white flex flex-col">
        <div className="bg-[#f5f5f5] border-b border-[#cccccc] p-3 px-4 font-bold text-sm tracking-widest flex items-center gap-2 text-[#0F172A] shrink-0">
          <TrendingUp className="w-5 h-5" />
          Live Network Traffic — ARP Packets Per Second
          {isOverLimit && (
            <span className="ml-auto bg-[#DC2626] text-white px-3 py-1 text-[10px] font-bold uppercase tracking-widest animate-pulse">
              HIGH-VOLUME ATTACK IN PROGRESS
            </span>
          )}
        </div>
        <div className="p-4" style={{ height: 260 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={displayData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="gradPPS" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#1E3A8A" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#1E3A8A" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="gradBlocked" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#DC2626" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#DC2626" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid key="grid-area" strokeDasharray="3 3" stroke="#E2E8F0" />
              <XAxis
                key="xaxis-area"
                dataKey="time"
                tick={{ fontSize: 9, fontFamily: 'JetBrains Mono', fill: '#94A3B8' }}
                interval="preserveStartEnd"
              />
              <YAxis key="yaxis-area" tick={{ fontSize: 9, fontFamily: 'JetBrains Mono', fill: '#94A3B8' }} />
              <Tooltip key="tooltip-area" content={<CustomTooltip />} />
              <Legend
                key="legend-area"
                wrapperStyle={{ fontSize: 10, fontFamily: 'JetBrains Mono', textTransform: 'uppercase', letterSpacing: '0.1em' }}
              />
              <ReferenceLine
                key="refline-area"
                y={arpFloodLimit}
                stroke="#DC2626"
                strokeDasharray="6 3"
                label={{ value: `FLOOD LIMIT: ${arpFloodLimit}`, position: 'insideTopRight', fill: '#DC2626', fontSize: 9, fontFamily: 'JetBrains Mono' }}
              />
              <Area key="area-pps"     type="monotone" dataKey="pps"     stroke="#1E3A8A" strokeWidth={2} fill="url(#gradPPS)"     name="ARP PPS"    dot={false} />
              <Area key="area-blocked" type="monotone" dataKey="blocked" stroke="#DC2626" strokeWidth={2} fill="url(#gradBlocked)" name="Blocked PPS" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* Analytics: Daily / Weekly (Hourly profile or Weekday totals) */}
      <section className="border border-[#cccccc] bg-white flex flex-col">
        <div className="bg-[#f5f5f5] border-b border-[#cccccc] p-3 px-4 font-bold text-sm tracking-widest flex items-center gap-2 text-[#0F172A] shrink-0">
          <BarChart2 className="w-5 h-5" />
          Analytics — Daily / Weekly
          <div className="ml-auto flex items-center gap-2">
            <button onClick={() => setPeriod('daily')} className={`px-3 py-1 text-xs font-bold uppercase tracking-widest ${period==='daily' ? 'bg-[#1E3A8A] text-white' : 'bg-white text-[#0F172A] border'} rounded`}>Daily</button>
            <button onClick={() => setPeriod('weekly')} className={`px-3 py-1 text-xs font-bold uppercase tracking-widest ${period==='weekly' ? 'bg-[#1E3A8A] text-white' : 'bg-white text-[#0F172A] border'} rounded`}>Weekly</button>
            <button onClick={() => setUseMock(v => !v)} className={`px-3 py-1 text-xs font-bold uppercase tracking-widest ${useMock ? 'bg-[#16A34A] text-white' : 'bg-white text-[#0F172A] border'} rounded`}>
              {useMock ? 'Demo On' : 'Demo Off'}
            </button>
          </div>
        </div>
        <div className="p-4" style={{ height: 220 }}>
          {period === 'daily' ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={hourlyProfile} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                <XAxis dataKey="label" tick={{ fontSize: 9, fontFamily: 'JetBrains Mono', fill: '#94A3B8' }} />
                <YAxis tick={{ fontSize: 9, fontFamily: 'JetBrains Mono', fill: '#94A3B8' }} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: 10, fontFamily: 'JetBrains Mono', textTransform: 'uppercase', letterSpacing: '0.1em' }} />
                <Bar dataKey="pps" name="Avg PPS (hour)" fill="#1E3A8A" maxBarSize={40} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={weekdayProfile} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                <XAxis dataKey="label" tick={{ fontSize: 9, fontFamily: 'JetBrains Mono', fill: '#94A3B8' }} />
                <YAxis tick={{ fontSize: 9, fontFamily: 'JetBrains Mono', fill: '#94A3B8' }} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: 10, fontFamily: 'JetBrains Mono', textTransform: 'uppercase', letterSpacing: '0.1em' }} />
                <Bar dataKey="pps" name="Total PPS (weekday)" fill="#1E3A8A" maxBarSize={40} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </section>

      {/* 24h historical distribution */}
      <section className="border border-[#cccccc] bg-white flex flex-col">
        <div className="bg-[#f5f5f5] border-b border-[#cccccc] p-3 px-4 font-bold text-sm tracking-widest flex items-center gap-2 text-[#0F172A] shrink-0">
          <BarChart2 className="w-5 h-5" />
          Threat Incident Distribution — Last 24 Hours (Simulated Historical)
        </div>
        <div className="p-4" style={{ height: 200 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={HOURLY_DATA} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid key="grid-bar" strokeDasharray="3 3" stroke="#E2E8F0" />
              <XAxis key="xaxis-bar" dataKey="hour" tick={{ fontSize: 9, fontFamily: 'JetBrains Mono', fill: '#94A3B8' }} interval={1} />
              <YAxis key="yaxis-bar" tick={{ fontSize: 9, fontFamily: 'JetBrains Mono', fill: '#94A3B8' }} />
              <Tooltip key="tooltip-bar" content={<CustomTooltip />} />
              <Legend key="legend-bar" wrapperStyle={{ fontSize: 10, fontFamily: 'JetBrains Mono', textTransform: 'uppercase', letterSpacing: '0.1em' }} />
              <Bar key="bar-incidents" dataKey="incidents" fill="#1E3A8A" name="Total Incidents" maxBarSize={20} />
              <Bar key="bar-blocked"   dataKey="blocked"   fill="#16A34A" name="Blocked"         maxBarSize={20} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

    </div>
  );
}
