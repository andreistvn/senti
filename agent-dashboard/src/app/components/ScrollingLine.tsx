import React, { useEffect, useRef } from 'react';

interface ScrollingLineProps {
  // Oldest first. The last value is the newest reading.
  values: number[];
  // How often a new value arrives; the line takes this long to move one step.
  intervalMs: number;
  height?: number;
  stroke?: string;
}

// The y-axis never zooms in further than this, so an idle agent's 0–1% jitter
// reads as a nearly flat line rather than filling the whole chart.
const MIN_SCALE_MAX = 5;

/**
 * A line that glides continuously from right to left, like a patient monitor.
 *
 * Each point is one step apart and the whole line is slid left by one step over
 * `intervalMs`; when the next reading arrives the data shifts by one and the
 * slide starts again from zero, so the two cancel out and the motion is
 * seamless. The newest point is drawn just past the right edge and slides in,
 * which is why the chart shows one step less than it is given.
 *
 * The slide is applied straight to the DOM on each animation frame — going
 * through React state would re-render the dashboard sixty times a second.
 */
export default function ScrollingLine({ values, intervalMs, height = 80, stroke = '#1a4fd6' }: ScrollingLineProps) {
  const groupRef = useRef<SVGGElement>(null);
  const arrivedAt = useRef(performance.now());

  // A new reading has just been appended: restart the slide.
  useEffect(() => {
    arrivedAt.current = performance.now();
  }, [values]);

  useEffect(() => {
    const still = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    let frame = 0;
    const tick = () => {
      const progress = still ? 1 : Math.min(1, (performance.now() - arrivedAt.current) / intervalMs);
      groupRef.current?.setAttribute('transform', `translate(${-progress} 0)`);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [intervalMs]);

  // One unit of x per step; the viewBox is one step narrower than the data so
  // the newest point starts off-screen.
  const steps = Math.max(1, values.length - 2);
  const top = Math.max(MIN_SCALE_MAX, ...values) * 1.1;
  const points = values.map((v, i) => `${i},${(100 - (v / top) * 100).toFixed(2)}`).join(' ');

  return (
    <svg
      width="100%"
      height={height}
      viewBox={`0 -4 ${steps} 108`}
      preserveAspectRatio="none"
      role="img"
      aria-label="CPU load over the last minute"
      style={{ display: 'block', overflow: 'hidden' }}
    >
      <g ref={groupRef}>
        <polyline
          points={points}
          fill="none"
          stroke={stroke}
          strokeWidth={2}
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
      </g>
    </svg>
  );
}
