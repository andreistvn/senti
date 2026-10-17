// A small "i" marker that reveals an explanation on hover (native title
// tooltip — no provider wiring, works everywhere). Used to explain fields the
// panel asked about, e.g. model confidence.
export function InfoHint({ text, className = '' }: { text: string; className?: string }) {
  return (
    <span
      title={text}
      aria-label={text}
      role="img"
      className={
        'ml-1 inline-flex h-3.5 w-3.5 items-center justify-center rounded-full ' +
        'border border-current align-middle text-[8px] font-bold leading-none ' +
        'text-[#94A3B8] cursor-help select-none ' +
        className
      }
    >
      i
    </span>
  );
}
