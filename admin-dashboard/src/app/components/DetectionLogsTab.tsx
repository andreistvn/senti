import React, { useMemo, useState } from 'react';
import type { AdminBlacklistEntry } from '../lib/adminApi';
import {
  parseDetection, actionTone, ACTION_COLOR, toCSV, downloadCSV,
  type RawLog, type Detection,
} from '../lib/detections';
import { confidenceColor, confidenceLegend } from '../lib/confidence';
import { InfoHint } from './InfoHint';

// Every detection the agents reported, as a filterable log — including events
// that were NOT blocked, so an operator can see the full picture rather than
// only the blacklisted incidents.

type ActionFilter = 'all' | 'blocked' | 'detected';

export default function DetectionLogsTab({
  logs,
  blacklist,
  thresholdPct,
}: {
  logs: RawLog[];
  blacklist: AdminBlacklistEntry[];
  thresholdPct: number;
}) {
  const [query, setQuery] = useState('');
  const [tier, setTier] = useState('all');
  const [action, setAction] = useState<ActionFilter>('all');
  const [onlyDetections, setOnlyDetections] = useState(true);

  // MAC → confidence, for rows that arrive without their own (older records).
  const confByMac = useMemo(() => {
    const map = new Map<string, string>();
    blacklist.forEach(b => map.set(b.mac.toUpperCase(), b.confidence));
    return map;
  }, [blacklist]);

  const detections = useMemo(() => logs.map(parseDetection), [logs]);

  const tiers = useMemo(() => {
    const set = new Set<string>();
    detections.forEach(d => { if (d.isDetection) set.add(d.tier); });
    return Array.from(set).sort();
  }, [detections]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return detections.filter(d => {
      if (onlyDetections && !d.isDetection) return false;
      if (tier !== 'all' && d.tier !== tier) return false;
      if (action !== 'all' && actionTone(d.action) !== action) return false;
      if (q && !d.raw.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [detections, query, tier, action, onlyDetections]);

  const confOf = (d: Detection) => d.confidence || confByMac.get(d.sourceMac.toUpperCase()) || '';

  const handleExport = () => {
    const csv = toCSV(filtered, [
      { header: 'Time', get: d => d.timestamp },
      { header: 'Tier', get: d => d.tier },
      { header: 'Attack Type', get: d => d.attackType },
      { header: 'Source MAC', get: d => d.sourceMac },
      { header: 'Detection Confidence', get: d => confOf(d) },
      { header: 'Action', get: d => d.action },
      { header: 'Detail', get: d => d.detail },
    ]);
    downloadCSV(`sentinet-detections-${new Date().toISOString().slice(0, 10)}.csv`, csv);
  };

  const selectCls =
    "bg-white border border-[#cbd5e1] text-xs px-2 py-1.5 font-['JetBrains_Mono',_monospace] text-[#0F172A]";

  return (
    <section className="border border-[#cccccc] bg-white flex flex-col min-h-0 flex-1">
      {/* Header + filters */}
      <div className="bg-[#f5f5f5] border-b border-[#cccccc] p-3 px-4 flex flex-wrap items-center gap-3 shrink-0">
        <span className="font-bold text-sm tracking-widest text-[#0F172A]">Detection Logs</span>
        <span className="text-[10px] text-[#64748b] font-['JetBrains_Mono',_monospace]">
          {filtered.length} / {onlyDetections ? detections.filter(d => d.isDetection).length : detections.length} shown
        </span>

        <div className="ml-auto flex flex-wrap items-center gap-2">
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search MAC, type, detail…"
            className={selectCls + ' w-48'}
          />
          <select value={tier} onChange={e => setTier(e.target.value)} className={selectCls}>
            <option value="all">All tiers</option>
            {tiers.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <select value={action} onChange={e => setAction(e.target.value as ActionFilter)} className={selectCls}>
            <option value="all">All actions</option>
            <option value="blocked">Blocked</option>
            <option value="detected">Detected only</option>
          </select>
          <label className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-[#475569] cursor-pointer select-none">
            <input type="checkbox" checked={onlyDetections} onChange={e => setOnlyDetections(e.target.checked)} />
            Detections only
          </label>
          <button
            onClick={handleExport}
            disabled={filtered.length === 0}
            className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest bg-[#0d1b3e] text-white disabled:opacity-40"
          >
            Export CSV
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 min-h-0 overflow-auto">
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
                <th className="p-3 border-r border-[#e2e8f0]">Detection Confidence<InfoHint text={confidenceLegend(thresholdPct)} /></th>
                <th className="p-3 border-r border-[#e2e8f0]">Action</th>
                <th className="p-3">Detail</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(d => {
                const conf = confOf(d);
                return (
                  <tr key={d.id} className="border-b border-[#e2e8f0] hover:bg-slate-50 transition align-top">
                    <td className="p-3 border-r border-[#e2e8f0] text-[#64748B] whitespace-nowrap">{d.timestamp}</td>
                    <td className="p-3 border-r border-[#e2e8f0] whitespace-nowrap">{d.tier}</td>
                    <td className="p-3 border-r border-[#e2e8f0] font-bold text-[#0F172A]">{d.attackType}</td>
                    <td className="p-3 border-r border-[#e2e8f0]">{d.sourceMac || '—'}</td>
                    <td className="p-3 border-r border-[#e2e8f0] font-bold" style={{ color: conf ? confidenceColor(conf, thresholdPct) : '#94A3B8' }}>
                      {conf || '—'}
                    </td>
                    <td className="p-3 border-r border-[#e2e8f0] font-bold whitespace-nowrap" style={{ color: ACTION_COLOR[actionTone(d.action)] }}>
                      {d.action}
                    </td>
                    <td className="p-3 text-[#475569] max-w-[320px] break-words">{d.detail || '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="border-t border-[#e2e8f0] p-2 px-4 text-[9px] text-[#94A3B8] uppercase tracking-widest shrink-0">
        Red = blocked · Amber = detected, not blocked · Detection confidence = model score that got the MAC blacklisted (Tier 1/3 rows inherit it)
      </div>
    </section>
  );
}
