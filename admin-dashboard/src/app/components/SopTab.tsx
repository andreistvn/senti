import React from 'react';

interface SopMetric {
  label: string;
  unit?: string;
}

interface SopCard {
  key: string;
  title: string;
  scenarios?: string[];
  // Each inner array is one row of boxes, split into equal widths.
  rows: SopMetric[][];
}

const ROW_COLS: Record<number, string> = {
  1: 'grid-cols-1',
  2: 'grid-cols-2',
  3: 'grid-cols-3',
  4: 'grid-cols-4',
};

// UI only — values are placeholders until the experiment data is wired in.
// Scope is the SentiNet agent; the Traditional IDPS baseline is recorded elsewhere.
const SOP_CARDS: SopCard[] = [
  {
    key: 'SOP 1',
    title: 'System Efficiency',
    scenarios: ['Normal', 'Poisoning', 'Flooding'],
    rows: [
      [{ label: 'Mean CPU', unit: '%' }, { label: 'Mean RAM', unit: 'MB' }],
    ],
  },
  {
    key: 'SOP 2',
    title: 'Detection Performance',
    rows: [
      [
        { label: 'True Positives' },
        { label: 'False Positives' },
        { label: 'True Negatives' },
        { label: 'False Negatives' },
      ],
      [{ label: 'Accuracy', unit: '%' }],
      [
        { label: 'Blocked Attacks' },
        { label: 'Total Detected Attacks' },
        { label: 'Prevention Rate', unit: '%' },
      ],
    ],
  },
  {
    key: 'SOP 3',
    title: 'Time-to-Block',
    rows: [
      [{ label: 'T-Enforced' }, { label: 'T-Detected' }, { label: 'TTB', unit: 'ms' }],
    ],
  },
];

function MetricCell({ metric }: { metric: SopMetric }) {
  return (
    <div className="p-3 border border-[#E2E8F0] bg-[#F8FAFC] flex flex-col gap-0.5">
      <span className="text-[9px] uppercase tracking-widest text-[#94A3B8]">{metric.label}</span>
      <span className="font-['JetBrains_Mono',_monospace] text-lg font-bold text-[#0F172A]">
        —{metric.unit && <span className="text-[10px] text-[#94A3B8] ml-1">{metric.unit}</span>}
      </span>
    </div>
  );
}

export default function SopTab() {
  return (
    <div className="flex flex-col gap-4">

      <section className="border border-[#cccccc] bg-white">
        <div className="bg-[#f5f5f5] p-3 px-4 font-bold text-sm tracking-widest flex items-center gap-2 text-[#0F172A]">
          Statement of the Problem
          <span className="ml-auto font-['JetBrains_Mono',_monospace] text-[#1E3A8A] text-xs">SENTINET AGENT</span>
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {SOP_CARDS.map(sop => (
          <section key={sop.key} className="border border-[#cccccc] bg-white flex flex-col">
            <div className="bg-[#f5f5f5] border-b border-[#cccccc] p-3 px-4 font-bold text-sm tracking-widest flex items-center gap-2 text-[#0F172A] shrink-0">
              {sop.title}
            </div>

            <div className="flex-1 p-4 flex flex-col gap-3">
              {(sop.scenarios ?? [null]).map(scenario => (
                <div key={scenario ?? sop.key} className="flex flex-col gap-3">
                  {scenario && (
                    <div className="text-[10px] font-bold uppercase tracking-widest text-[#64748B]">{scenario}</div>
                  )}
                  {sop.rows.map((row, i) => (
                    <div key={i} className={`grid gap-3 ${ROW_COLS[row.length]}`}>
                      {row.map(m => <MetricCell key={m.label} metric={m} />)}
                    </div>
                  ))}
                </div>
              ))}
            </div>

            <div className="border-t border-[#e2e8f0] p-3 px-4 text-[10px] text-[#94A3B8] uppercase tracking-widest">
              Awaiting experiment data
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
