import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useTrayConnection } from '../hooks/useTrayConnection';

interface DetectionLog {
  id: number;
  timestamp: string;
  sourceMac: string;
  attackType: string;
  tier: string;
  action: string;
}

export function useDashboardState(intervalMs = 1000) {
  const [cpuData, setCpuData] = useState(
    // A minute of readings, plus the one sliding in from the right edge and
    // the one sliding out at the left (see ScrollingLine).
    Array.from({ length: 62 }, (_, i) => ({ time: i, usage: 0 }))
  );

  const tray = useTrayConnection(intervalMs);
  const live = tray.connected;
  const liveCpu = tray.stats?.cpu ?? 0;

  // Hold the latest reading in a ref so the interval below can read it without
  // being listed as a dependency. It used to depend on liveCpu directly, which
  // meant React tore down and recreated the timer every time the value changed,
  // restarting the countdown each time — that is why the line advanced in fits
  // and starts rather than at a steady rate.
  const liveCpuRef = useRef(liveCpu);
  liveCpuRef.current = liveCpu;

  useEffect(() => {
    const interval = setInterval(() => {
      setCpuData(prev => [
        ...prev.slice(1),
        { time: prev[prev.length - 1].time + 1, usage: liveCpuRef.current },
      ]);
    }, intervalMs);

    return () => clearInterval(interval);
  }, [intervalMs]);

  // Expose ONLY real data. No mock fallback.
  const eProtected = tray.status?.protected ?? false;
  const eRelayOnline = tray.status?.relay === 'online';
  const eNetwork = tray.status?.network ?? '';
  const eInspected = tray.stats?.inspected ?? 0;
  const eDropped = tray.stats?.dropped ?? 0;
  const ePassed = tray.stats?.passed ?? 0;
  const eMemory = tray.stats?.memory ?? 0;
  const eMemoryMb = tray.stats?.memoryMb ?? 0;
  const eIdentity = tray.stats?.identity ?? { hostname: '', ip: '', mac: '' };
  const eBlacklist = tray.stats?.blacklist ?? [];
  const eSigContrib = tray.stats?.bayanihan?.contributions ?? 0;
  // Reports this agent has queued for the relay but that haven't been
  // acknowledged yet — see bayanihan_client.py's pending-report queue. Shown
  // so a relay outage (or a report still retrying) is visible here instead of
  // only showing up later as a gap on the admin dashboard.
  const eReportsPending = tray.stats?.bayanihan?.pending ?? 0;
  const eLastThreat = tray.stats?.lastThreat ?? null;
  const eLogs = (live && tray.events) ? tray.events : [];

  const detectionLogsContainerRef = useRef<HTMLDivElement>(null);
  const prevDetectionLogsSnapshotRef = useRef<{ length: number; scrollTop: number; scrollHeight: number; clientHeight: number } | null>(null);

  useLayoutEffect(() => {
    const c = detectionLogsContainerRef.current;
    const prev = prevDetectionLogsSnapshotRef.current;
    if (!c) {
      prevDetectionLogsSnapshotRef.current = null;
      return;
    }

    if (!prev) {
      prevDetectionLogsSnapshotRef.current = { length: eLogs.length, scrollTop: c.scrollTop, scrollHeight: c.scrollHeight, clientHeight: c.clientHeight };
      return;
    }

    prevDetectionLogsSnapshotRef.current = { length: eLogs.length, scrollTop: c.scrollTop, scrollHeight: c.scrollHeight, clientHeight: c.clientHeight };
  }, [eLogs]);

  return {
    cpuData,
    cpuIntervalMs: intervalMs,
    lastUpdate: 0, // Not used as much anymore, or can be static
    eProtected,
    eRelayOnline,
    eNetwork,
    eInspected,
    eDropped,
    ePassed,
    eMemory,
    eMemoryMb,
    eIdentity,
    eBlacklist,
    eSigContrib,
    eReportsPending,
    eLastThreat,
    eLogs,
    detectionLogsContainerRef,
    live,
    tray,
  };
}
