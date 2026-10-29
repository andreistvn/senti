import React, { useMemo, useState } from 'react';
import type { AdminBlacklistEntry, AdminBlockchainMetrics } from '../lib/adminApi';
import {
  parseDetection, actionTone, ACTION_COLOR, toCSV, downloadCSV, type RawLog, type Detection,
} from '../lib/detections';
import { confidenceColor, confidenceLegend } from '../lib/confidence';
import { InfoHint } from './InfoHint';

// A generated report over the detections the dashboard has collected: a metrics
// summary plus a filtered table, exportable to CSV or print. All aggregation is
// client-side over data already fetched — no backend report endpoint required.

type ActionFilter = 'all' | 'blocked' | 'detected';

// `from` / `to` come from datetime-local inputs ("2026-10-30T09:30"). Records
// are kept across relay restarts and days, so the range is checked against the
// relay's receive time. A record without one can only be placed by its clock
// time, so it is compared on HH:MM alone.
function withinRange(d: Detection, from: string, to: string): boolean {
  if (d.createdMs != null) {
    if (from && d.createdMs < new Date(from).getTime()) return false;
    // `to` is inclusive of its whole minute.
    if (to && d.createdMs >= new Date(to).getTime() + 60_000) return false;
    return true;
  }
  const hm = d.timestamp.slice(0, 5);
  if (from && hm < from.slice(11, 16)) return false;
  if (to && hm > to.slice(11, 16)) return false;
  return true;
}

function pad(n: number) {
  return String(n).padStart(2, '0');
}

// "2026-10-30 09:30:15" when the record has a date, else its clock time.
function stampOf(d: Detection): string {
  if (d.createdMs == null) return d.timestamp;
  const t = new Date(d.createdMs);
  return `${t.getFullYear()}-${pad(t.getMonth() + 1)}-${pad(t.getDate())} ${d.timestamp}`;
}

function StatCard({ label, value, color, small }: { label: string; value: number | string; color?: string; small?: boolean }) {
  return (
    <div className="border border-[#e2e8f0] bg-white p-4 flex flex-col gap-1">
      <span className="text-[#94A3B8] text-[10px] uppercase tracking-widest">{label}</span>
      <span className={`font-['JetBrains_Mono',_monospace] font-bold ${small ? 'text-sm break-words' : 'text-3xl'}`} style={{ color: color ?? '#0F172A' }}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </span>
    </div>
  );
}

function TopList({ title, rows }: { title: string; rows: [string, number][] }) {
  return (
    <section className="border border-[#cccccc] bg-white flex flex-col">
      <div className="bg-[#f5f5f5] border-b border-[#cccccc] p-3 px-4 font-bold text-sm tracking-widest text-[#0F172A]">{title}</div>
      <div className="p-2">
        {rows.length === 0 ? (
          <p className="p-2 text-[#64748b] text-xs">No data in range.</p>
        ) : (
          <table className="w-full text-xs font-['JetBrains_Mono',_monospace]">
            <tbody>
              {rows.map(([k, n]) => (
                <tr key={k} className="border-b border-[#f1f5f9] last:border-0">
                  <td className="py-1.5 px-2 text-[#0F172A] break-all">{k || '—'}</td>
                  <td className="py-1.5 px-2 text-right font-bold text-[#0F172A] w-16">{n.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}

function topN(counts: Map<string, number>, n: number): [string, number][] {
  return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]).slice(0, n);
}

export default function ReportsTab({
  logs,
  blacklist,
  blockchainMetrics,
  connectedAgents,
  thresholdPct,
}: {
  logs: RawLog[];
  blacklist: AdminBlacklistEntry[];
  blockchainMetrics: AdminBlockchainMetrics;
  connectedAgents: number;
  thresholdPct: number;
}) {
  const [query, setQuery] = useState('');
  const [tier, setTier] = useState('all');
  const [action, setAction] = useState<ActionFilter>('all');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');

  const detections = useMemo(
    () => logs.map(parseDetection).filter(d => d.isDetection),
    [logs],
  );

  const tiers = useMemo(() => Array.from(new Set(detections.map(d => d.tier))).sort(), [detections]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return detections.filter(d => {
      if (tier !== 'all' && d.tier !== tier) return false;
      if (action !== 'all' && actionTone(d.action) !== action) return false;
      if (!withinRange(d, from, to)) return false;
      if (q && !d.raw.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [detections, query, tier, action, from, to]);

  const metrics = useMemo(() => {
    const blocked = filtered.filter(d => actionTone(d.action) === 'blocked').length;
    const detectedOnly = filtered.filter(d => actionTone(d.action) === 'detected').length;
    const byType = new Map<string, number>();
    const byMac = new Map<string, number>();
    filtered.forEach(d => {
      byType.set(d.attackType, (byType.get(d.attackType) ?? 0) + 1);
      if (d.sourceMac) byMac.set(d.sourceMac, (byMac.get(d.sourceMac) ?? 0) + 1);
    });
    return {
      total: filtered.length,
      blocked,
      detectedOnly,
      uniqueMacs: byMac.size,
      topTypes: topN(byType, 5),
      topMacs: topN(byMac, 5),
    };
  }, [filtered]);

  const rangeLabel = (from || to)
    ? `${from ? from.replace('T', ' ') : 'start'} – ${to ? to.replace('T', ' ') : 'now'}`
    : 'all records';

  const handleExport = () => {
    const summary =
      `SentiNet Detection Report\n` +
      `Generated,${new Date().toISOString()}\n` +
      `Time range,${rangeLabel}\n` +
      `Tier,${tier}\n` +
      `Action,${action}\n` +
      `Total detections,${metrics.total}\n` +
      `Blocked,${metrics.blocked}\n` +
      `Detected only,${metrics.detectedOnly}\n` +
      `Unique source MACs,${metrics.uniqueMacs}\n` +
      `Blacklisted MACs (network now),${blacklist.length}\n` +
      `Connected agents (now),${connectedAgents}\n` +
      `Total incidents (ledger),${blockchainMetrics.totalIncidents}\n` +
      `ML threshold,${thresholdPct.toFixed(0)}%\n\n`;
    const rows = toCSV(filtered, [
      { header: 'Time', get: d => stampOf(d) },
      { header: 'Tier', get: d => d.tier },
      { header: 'Attack Type', get: d => d.attackType },
      { header: 'Source MAC', get: d => d.sourceMac },
      { header: 'Confidence', get: d => d.confidence },
      { header: 'Action', get: d => d.action },
      { header: 'Detail', get: d => d.detail },
    ]);
    downloadCSV(`sentinet-report-${new Date().toISOString().slice(0, 10)}.csv`, summary + rows);
  };

  const selectCls =
    "bg-white border border-[#cbd5e1] text-xs px-2 py-1.5 font-['JetBrains_Mono',_monospace] text-[#0F172A]";

  return (
    <div className="flex flex-col gap-4">
      {/* Filter bar */}
      <section className="border border-[#cccccc] bg-white p-3 px-4 flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-[9px] uppercase tracking-widest text-[#94A3B8]">Search</label>
          <input value={query} onChange={e => setQuery(e.target.value)} placeholder="MAC, type, detail…" className={selectCls + ' w-44'} />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[9px] uppercase tracking-widest text-[#94A3B8]">Tier</label>
          <select value={tier} onChange={e => setTier(e.target.value)} className={selectCls}>
            <option value="all">All</option>
            {tiers.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[9px] uppercase tracking-widest text-[#94A3B8]">Action</label>
          <select value={action} onChange={e => setAction(e.target.value as ActionFilter)} className={selectCls}>
            <option value="all">All</option>
            <option value="blocked">Blocked</option>
            <option value="detected">Detected only</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[9px] uppercase tracking-widest text-[#94A3B8]">From</label>
          <input type="datetime-local" value={from} onChange={e => setFrom(e.target.value)} className={selectCls} />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[9px] uppercase tracking-widest text-[#94A3B8]">To</label>
          <input type="datetime-local" value={to} onChange={e => setTo(e.target.value)} className={selectCls} />
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button onClick={() => { setQuery(''); setTier('all'); setAction('all'); setFrom(''); setTo(''); }}
            className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest bg-white border border-[#cbd5e1] text-[#475569]">
            Reset
          </button>
          <button onClick={handleExport} disabled={filtered.length === 0}
            className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest bg-[#0d1b3e] text-white disabled:opacity-40">
            Export CSV
          </button>
          <button onClick={() => window.print()}
            className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest bg-white border border-[#cbd5e1] text-[#0F172A]">
            Print
          </button>
        </div>
      </section>

      {/* Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Detections" value={metrics.total} />
        <StatCard label="Blocked" value={metrics.blocked} color={ACTION_COLOR.blocked} />
        <StatCard label="Detected, Not Blocked" value={metrics.detectedOnly} color={ACTION_COLOR.detected} />
        <StatCard label="Unique Source MACs" value={metrics.uniqueMacs} />
        {/* These three describe the network as it is now, not the filtered rows. */}
        <StatCard label="Blacklisted MACs (Now)" value={blacklist.length} />
        <StatCard label="Connected Agents (Now)" value={connectedAgents} />
        <StatCard label="Total Incidents (Ledger)" value={blockchainMetrics.totalIncidents} />
        <StatCard label="Range" value={rangeLabel} small />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TopList title="Top Attack Types" rows={metrics.topTypes} />
        <TopList title="Top Source MACs" rows={metrics.topMacs} />
      </div>

      {/* Detail table */}
      <section className="border border-[#cccccc] bg-white flex flex-col">
        <div className="bg-[#f5f5f5] border-b border-[#cccccc] p-3 px-4 font-bold text-sm tracking-widest text-[#0F172A] flex justify-between items-center">
          <span>Report Detail</span>
          <span className="text-[10px] text-[#64748b] font-['JetBrains_Mono',_monospace]">{filtered.length} rows · {rangeLabel}</span>
        </div>
        <div className="overflow-auto max-h-[360px]">
          {filtered.length === 0 ? (
            <p className="p-4 text-[#64748b] text-xs">No detections match the current filters.</p>
          ) : (
            <table className="w-full text-left border-collapse font-['JetBrains_Mono',_monospace] text-xs">
              <thead className="bg-[#F8FAFC] border-b border-[#e2e8f0] sticky top-0 z-10 text-[10px] uppercase tracking-widest text-[#475569]">
                <tr>
                  <th className="p-3 border-r border-[#e2e8f0]">Time</th>
                  <th className="p-3 border-r border-[#e2e8f0]">Tier</th>
                  <th className="p-3 border-r border-[#e2e8f0]">Attack Type</th>
                  <th className="p-3 border-r border-[#e2e8f0]">Source MAC</th>
                  <th className="p-3 border-r border-[#e2e8f0]">Confidence<InfoHint text={confidenceLegend(thresholdPct)} /></th>
                  <th className="p-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(d => (
                  <tr key={d.id} className="border-b border-[#e2e8f0] hover:bg-slate-50 transition">
                    <td className="p-3 border-r border-[#e2e8f0] text-[#64748B] whitespace-nowrap">{stampOf(d)}</td>
                    <td className="p-3 border-r border-[#e2e8f0] whitespace-nowrap">{d.tier}</td>
                    <td className="p-3 border-r border-[#e2e8f0] font-bold text-[#0F172A]">{d.attackType}</td>
                    <td className="p-3 border-r border-[#e2e8f0]">{d.sourceMac || '—'}</td>
                    <td className="p-3 border-r border-[#e2e8f0] font-bold" style={{ color: d.confidence ? confidenceColor(d.confidence, thresholdPct) : '#94A3B8' }}>
                      {d.confidence || '—'}
                    </td>
                    <td className="p-3 font-bold whitespace-nowrap" style={{ color: ACTION_COLOR[actionTone(d.action)] }}>{d.action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  );
}
