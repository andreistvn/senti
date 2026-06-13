import React, { useMemo } from 'react';
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
  const peakPPS    = useMemo(() => Math.max(...data.map(d => d.pps)), [data]);
  const avgPPS     = useMemo(() => Math.round(data.reduce((s, d) => s + d.pps, 0) / Math.max(data.length, 1)), [data]);
  const currentPPS = data[data.length - 1]?.pps ?? 0;
  const isOverLimit = currentPPS >= arpFloodLimit;

  const statCards = [
    { label: 'Current ARP PPS',      value: currentPPS, unit: 'pps',      alert: isOverLimit },
    { label: 'Peak PPS (Session)',    value: peakPPS,    unit: 'pps',      alert: peakPPS >= arpFloodLimit },
    { label: 'Avg PPS (Session)',     value: avgPPS,     unit: 'pps',      alert: false },
    { label: 'Alert Threshold',       value: arpFloodLimit, unit: 'pps limit', alert: false },
  ];

  return (
    <div className="flex flex-col gap-4">

      {/* Stat summary row */}
      <div className="grid grid-cols-4 gap-4">
        {statCards.map(s => (
          <div
            key={s.label}
            className={`border-2 p-4 flex flex-col gap-1 ${s.alert ? 'border-[#DC2626] bg-[#FEF2F2]' : 'border-[#334155] bg-white'}`}
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
      <section className="border-2 border-[#334155] bg-white flex flex-col">
        <div className="bg-[#F1F5F9] border-b-2 border-[#334155] p-3 px-4 font-bold uppercase text-sm tracking-widest flex items-center gap-2 text-[#0F172A] shrink-0">
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
            <AreaChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
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

      {/* 24h historical distribution */}
      <section className="border-2 border-[#334155] bg-white flex flex-col">
        <div className="bg-[#F1F5F9] border-b-2 border-[#334155] p-3 px-4 font-bold uppercase text-sm tracking-widest flex items-center gap-2 text-[#0F172A] shrink-0">
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
