import React from 'react';
import * as Popover from '@radix-ui/react-popover';
import { Info } from 'lucide-react';
import { PANEL_GUIDES, POPOVER_LABELS, type PanelGuideId } from '../content/userGuide';

interface InfoPopoverProps {
  panel: PanelGuideId;
  /** 'dark' when the icon sits on a navy header. */
  tone?: 'light' | 'dark';
}

export default function InfoPopover({ panel, tone = 'light' }: InfoPopoverProps) {
  const guide = PANEL_GUIDES[panel];

  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button
          type="button"
          aria-label={`About ${guide.title}`}
          className={`shrink-0 inline-flex items-center justify-center p-0.5 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#c0392b] ${
            tone === 'dark' ? 'text-[#8899bb] hover:text-white' : 'text-[#888] hover:text-[#0d1b3e]'
          }`}
        >
          <Info size={14} aria-hidden="true" />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          side="bottom"
          align="end"
          sideOffset={6}
          collisionPadding={8}
          className="z-50 w-[320px] max-w-[calc(100vw-16px)] bg-white border border-[#cccccc] border-t-2 border-t-[#c0392b] shadow-lg p-4 space-y-3 focus:outline-none"
        >
          <p className="text-[#0d1b3e] text-[10px] tracking-widest uppercase font-bold">{guide.title}</p>
          <PopoverSection label={POPOVER_LABELS.what} text={guide.what} />
          {guide.how && <PopoverSection label={POPOVER_LABELS.how} text={guide.how} />}
          {guide.action && <PopoverSection label={POPOVER_LABELS.action} text={guide.action} />}
          <Popover.Arrow className="fill-[#c0392b]" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

function PopoverSection({ label, text }: { label: string; text: string }) {
  return (
    <div>
      <p className="text-[#888] text-[9px] tracking-widest uppercase mb-1">{label}</p>
      <p className="text-[#111] text-xs leading-relaxed">{text}</p>
    </div>
  );
}
