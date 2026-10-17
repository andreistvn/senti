import React, { useEffect, useState } from 'react';
import { getSopSummary, type SopScenario, type SopSummary } from '../lib/adminApi';
import { durationParts, formatDuration } from '../lib/format';

interface SopMetric {
  label: string;
  unit?: string;
  value?: string | null;
}

interface SopGroup {
  // Sub-heading above the rows, e.g. a traffic scenario.
  heading?: string;
  live?: boolean;
  // Each inner array is one row of boxes, split into equal widths.
  rows: SopMetric[][];
}

interface SopCard {
  key: string;
  title: string;
  groups: SopGroup[];
  // One entry per line.
  footer: string | string[];
}

const ROW_COLS: Record<number, string> = {
  1: 'grid-cols-1',
  2: 'grid-cols-2',
  3: 'grid-cols-3',
  4: 'grid-cols-4',
};

const SCENARIOS: { key: SopScenario; label: string }[] = [
  { key: 'normal', label: 'Normal' },
  { key: 'poisoning', label: 'Poisoning' },
  { key: 'flooding', label: 'Flooding' },
];

const POLL_MS = 2000;
const AWAITING = 'Awaiting experiment data';

function fixed(value: number | null | undefined, digits: number) {
  return value == null ? null : value.toFixed(digits);
}

// Epoch milliseconds as a wall-clock time with the milliseconds kept, since
// Time-to-Block is the difference between two of these.
function clockMs(ms: number | null | undefined) {
  if (ms == null) return null;
  const d = new Date(ms);
  const pad = (n: number, width = 2) => String(n).padStart(width, '0');
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${pad(d.getMilliseconds(), 3)}`;
}

// Scope is the SentiNet agent; the Traditional IDPS baseline is recorded elsewhere.
function buildCards(summary: SopSummary | null): SopCard[] {
  const scenarios = summary?.efficiency.scenarios;
  const readings = scenarios ? SCENARIOS.reduce((sum, s) => sum + scenarios[s.key].n, 0) : 0;
  const detection = summary?.detection;
  const evaluation = detection?.evaluation;
  const ttb = summary?.timeToBlock;
  const trial = ttb?.latest;

  const count = (value: number | null | undefined) => (value == null ? null : value.toLocaleString());

  // With an attacker declared for the run the matrix is the live one: the
  // agent's verdict on each packet against that ground truth. Otherwise it is
  // the model's result on the held-out test set, which in live mode drops to a
  // line of its own underneath.
  const attackerMacs = detection?.attackerMacs ?? [];
  const liveMode = attackerMacs.length > 0;
  const live = detection?.live;
  const matrix = liveMode ? live : evaluation;
  const latency = detection?.latency;
  const latencyText = latency
    ? `last detection after ${latency.packets} packets, ${formatDuration(latency.ms)}`
    : null;

  const detectionLines: string[] = [];
  if (liveMode) {
    const run = [`Live run · attacker ${attackerMacs.join(', ')}`];
    run.push(live ? `n = ${live.n.toLocaleString()} packets` : "waiting for the agent's counts");
    if (latencyText) run.push(latencyText);
    detectionLines.push(run.join(' · '));
    if (evaluation) {
      detectionLines.push(
        `Model validation · ${evaluation.accuracy.toFixed(2)}% accuracy on ${evaluation.n} held-out windows · threshold ${evaluation.threshold.toFixed(2)}`,
      );
    }
  } else if (evaluation) {
    const validation = [`Held-out test set · n = ${evaluation.n} windows · threshold ${evaluation.threshold.toFixed(2)}`];
    if (latencyText) validation.push(latencyText);
    detectionLines.push(validation.join(' · '));
  }
  if (detection?.totalDetectedAttacks != null) {
    detectionLines.push(
      detection.enforcement === 'simulated'
        ? "Prevention · attack packets counted live · this agent's OS cannot drop packets, so none are blocked"
        : 'Prevention · attack packets counted live · blocked = dropped by the kernel',
    );
  }

  let ttbFooter = AWAITING;
  if (trial && ttb) {
    const parts = [
      `Attacker ${trial.attackerMac}`,
      `detected by ${trial.detectedBy}`,
      trial.enforcedBy ? `enforced by ${trial.enforcedBy}` : 'awaiting enforcement by another agent',
    ];
    if (ttb.n > 0) {
      parts.push(`n = ${ttb.n}`);
      parts.push(`mean ${formatDuration(ttb.meanTtbMs, 1)}`);
      if (ttb.varianceTtbMs != null) parts.push(`variance ${fixed(ttb.varianceTtbMs, 1)}`);
    }
    if (trial.ttbMs != null && trial.agentClockTtbMs != null) {
      const skew = Math.abs(trial.agentClockTtbMs - trial.ttbMs);
      if (skew >= 50) parts.push(`agent clocks ${formatDuration(skew, 0)} apart, corrected`);
    }
    ttbFooter = parts.join(' · ');
  }

  return [
    {
      key: 'SOP 1',
      title: 'System Efficiency',
      groups: SCENARIOS.map(({ key, label }) => {
        const s = scenarios?.[key];
        return {
          heading: s && s.n > 0 ? `${label} · n = ${s.n}` : label,
          live: s?.live,
          rows: [[
            { label: 'Mean CPU', unit: '%', value: fixed(s?.meanCpu, 2) },
            { label: 'Mean RAM', unit: 'MB', value: fixed(s?.meanRamMb, 1) },
          ]],
        };
      }),
      footer: readings > 0 && summary
        ? `${summary.efficiency.agent ?? 'Agent'} · ${readings} snapshots · one per ${summary.efficiency.sampleIntervalSeconds}s per scenario`
        : AWAITING,
    },
    {
      key: 'SOP 2',
      title: 'Detection Performance',
      groups: [{
        rows: [
          [
            { label: 'True Positives', value: count(matrix?.truePositives) },
            { label: 'False Positives', value: count(matrix?.falsePositives) },
            { label: 'True Negatives', value: count(matrix?.trueNegatives) },
            { label: 'False Negatives', value: count(matrix?.falseNegatives) },
          ],
          [
            { label: 'Accuracy', unit: '%', value: fixed(matrix?.accuracy, 2) },
            { label: 'Detection Rate', unit: '%', value: fixed(matrix?.detectionRate, 2) },
            { label: 'False Positive Rate', unit: '%', value: fixed(matrix?.falsePositiveRate, 2) },
          ],
          [
            { label: 'Blocked Attacks', value: count(detection?.blockedAttacks) },
            { label: 'Total Detected Attacks', value: count(detection?.totalDetectedAttacks) },
            { label: 'Prevention Rate', unit: '%', value: fixed(detection?.preventionRate, 2) },
          ],
        ],
      }],
      footer: detectionLines.length > 0 ? detectionLines : AWAITING,
    },
    {
      key: 'SOP 3',
      title: 'Time-to-Block',
      groups: [{
        rows: [[
          { label: 'T-Enforced', value: clockMs(trial?.tEnforcedMs) },
          { label: 'T-Detected', value: clockMs(trial?.tDetectedMs) },
          { label: 'TTB', ...durationParts(trial?.ttbMs, 0) },
        ]],
      }],
      footer: ttbFooter,
    },
  ];
}

function MetricCell({ metric }: { metric: SopMetric }) {
  return (
    <div className="p-3 border border-[#E2E8F0] bg-[#F8FAFC] flex flex-col gap-0.5">
      <span className="text-[9px] uppercase tracking-widest text-[#94A3B8]">{metric.label}</span>
      <span className="font-['JetBrains_Mono',_monospace] text-lg font-bold text-[#0F172A]">
        {metric.value ?? '—'}{metric.unit && <span className="text-[10px] text-[#94A3B8] ml-1">{metric.unit}</span>}
      </span>
    </div>
  );
}

export default function SopTab() {
  const [summary, setSummary] = useState<SopSummary | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const next = await getSopSummary();
      if (alive) setSummary(next);
    };
    void load();
    const poll = setInterval(load, POLL_MS);
    return () => {
      alive = false;
      clearInterval(poll);
    };
  }, []);

  return (
    <div className="flex flex-col gap-4">

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {buildCards(summary).map(sop => (
          <section key={sop.key} className="border border-[#cccccc] bg-white flex flex-col">
            <div className="bg-[#f5f5f5] border-b border-[#cccccc] p-3 px-4 font-bold text-sm tracking-widest flex items-center gap-2 text-[#0F172A] shrink-0">
              {sop.title}
            </div>

            <div className="flex-1 p-4 flex flex-col gap-3">
              {sop.groups.map((group, g) => (
                <div key={group.heading ?? g} className="flex flex-col gap-3">
                  {group.heading && (
                    <div className="text-[10px] font-bold uppercase tracking-widest text-[#64748B] flex items-center gap-2">
                      {group.heading}
                      {group.live && (
                        <span className="font-['JetBrains_Mono',_monospace] text-[9px] text-white bg-[#1E3A8A] px-1.5 py-0.5">LIVE</span>
                      )}
                    </div>
                  )}
                  {group.rows.map((row, i) => (
                    <div key={i} className={`grid gap-3 ${ROW_COLS[row.length]}`}>
                      {row.map(m => <MetricCell key={m.label} metric={m} />)}
                    </div>
                  ))}
                </div>
              ))}
            </div>

            <div className="border-t border-[#e2e8f0] p-3 px-4 text-[10px] text-[#94A3B8] uppercase tracking-widest">
              {(Array.isArray(sop.footer) ? sop.footer : [sop.footer]).map((line, i) => (
                <div key={i} className={i > 0 ? 'mt-1' : undefined}>{line}</div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
