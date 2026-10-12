import React from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import {
  GETTING_STARTED,
  GLOSSARY,
  GUIDE_BUTTON_LABEL,
  GUIDE_INTRO,
  GUIDE_TITLE,
  PANEL_GUIDES,
  PANEL_GUIDE_ORDER,
  PANELS_HEADING,
  POPOVER_LABELS,
  STATUS_COLORS,
  TROUBLESHOOTING,
} from '../content/userGuide';

interface UserGuideDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function UserGuideDialog({ open, onOpenChange }: UserGuideDialogProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Trigger asChild>
        <button
          type="button"
          className="flex items-center gap-2 text-[10px] tracking-widest uppercase px-3 py-1.5 border border-[#8899bb] text-white hover:bg-white/10 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-[#c0392b]"
        >
          {GUIDE_BUTTON_LABEL}
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-[#0d1b3e]/60" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed z-50 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[calc(100vw-32px)] max-w-3xl max-h-[85vh] flex flex-col bg-white border border-[#cccccc] shadow-xl focus:outline-none"
        >
          <div className="flex items-center justify-between gap-4 bg-[#0d1b3e] border-b-2 border-[#c0392b] px-5 py-3 shrink-0">
            <Dialog.Title className="flex items-center gap-2 text-white tracking-widest text-sm font-bold uppercase">
              {GUIDE_TITLE}
            </Dialog.Title>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="Close user guide"
                className="text-[#8899bb] hover:text-white transition-colors p-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#c0392b]"
              >
                <X size={16} aria-hidden="true" />
              </button>
            </Dialog.Close>
          </div>

          <div className="flex-1 overflow-y-auto p-5 space-y-6">
            <GuideSection heading={GUIDE_INTRO.heading}>
              <p className="text-[#111] text-xs leading-relaxed">{GUIDE_INTRO.body}</p>
            </GuideSection>

            <GuideSection heading={GETTING_STARTED.heading}>
              <ol className="list-decimal pl-5 space-y-1.5 text-[#111] text-xs leading-relaxed">
                {GETTING_STARTED.steps.map(step => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
            </GuideSection>

            <GuideSection heading={PANELS_HEADING}>
              <div className="space-y-3">
                {PANEL_GUIDE_ORDER.map(id => {
                  const guide = PANEL_GUIDES[id];
                  return (
                    <div key={id} className="border border-[#cccccc]">
                      <p className="px-3 py-2 border-b border-[#cccccc] bg-[#f5f5f5] text-[#0d1b3e] text-[10px] tracking-widest uppercase font-bold">
                        {guide.title}
                      </p>
                      <dl className="p-3 space-y-2">
                        <GuideField label={POPOVER_LABELS.what} text={guide.what} />
                        {guide.how && <GuideField label={POPOVER_LABELS.how} text={guide.how} />}
                        {guide.action && <GuideField label={POPOVER_LABELS.action} text={guide.action} />}
                      </dl>
                    </div>
                  );
                })}
              </div>
            </GuideSection>

            <GuideSection heading={STATUS_COLORS.heading}>
              <ul className="space-y-2">
                {STATUS_COLORS.items.map(item => (
                  <li key={item.label} className="flex items-start gap-3 text-xs leading-relaxed">
                    <span className="w-3 h-3 mt-0.5 shrink-0" style={{ background: item.color }} aria-hidden="true" />
                    <span className="text-[#111]">
                      <span className="font-bold">{item.label}</span> — {item.meaning}
                    </span>
                  </li>
                ))}
              </ul>
            </GuideSection>

            <GuideSection heading={TROUBLESHOOTING.heading}>
              <div className="overflow-x-auto border border-[#cccccc]">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-[#f5f5f5] border-b border-[#cccccc] text-[#555] text-[10px] tracking-widest uppercase">
                      <th scope="col" className="text-left px-3 py-2 font-bold w-1/3">{TROUBLESHOOTING.symptomLabel}</th>
                      <th scope="col" className="text-left px-3 py-2 font-bold">{TROUBLESHOOTING.fixLabel}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {TROUBLESHOOTING.rows.map(row => (
                      <tr key={row.symptom} className="border-t border-[#eee] align-top">
                        <td className="px-3 py-2 text-[#111] font-bold">{row.symptom}</td>
                        <td className="px-3 py-2 text-[#111] leading-relaxed">{row.fix}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </GuideSection>

            <GuideSection heading={GLOSSARY.heading}>
              <dl className="space-y-2">
                {GLOSSARY.terms.map(entry => (
                  <div key={entry.term} className="text-xs leading-relaxed">
                    <dt className="inline text-[#0d1b3e] font-bold">{entry.term}</dt>
                    <dd className="inline text-[#111]"> — {entry.definition}</dd>
                  </div>
                ))}
              </dl>
            </GuideSection>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function GuideSection({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="text-[#0d1b3e] text-[11px] tracking-widest uppercase font-bold border-l-2 border-[#c0392b] pl-2 mb-3">
        {heading}
      </h3>
      {children}
    </section>
  );
}

function GuideField({ label, text }: { label: string; text: string }) {
  return (
    <div>
      <dt className="text-[#888] text-[9px] tracking-widest uppercase mb-0.5">{label}</dt>
      <dd className="text-[#111] text-xs leading-relaxed whitespace-pre-line">{text}</dd>
    </div>
  );
}
