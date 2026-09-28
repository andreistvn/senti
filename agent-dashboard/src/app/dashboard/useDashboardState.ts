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

export function useDashboardState(intervalMs = 2000) {
  const [cpuData, setCpuData] = useState(
    Array.from({ length: 60 }, (_, i) => ({ time: i, usage: 0 }))
  );

  const tray = useTrayConnection(intervalMs);
  const live = tray.connected;
  const liveCpu = tray.stats?.cpu ?? 0;

  useEffect(() => {
    const interval = setInterval(() => {
      setCpuData(prev => [
        ...prev.slice(1),
        { time: prev[prev.length - 1].time + 1, usage: liveCpu },
      ]);
    }, intervalMs);

    return () => clearInterval(interval);
  }, [liveCpu, intervalMs]);

  // Expose ONLY real data. No mock fallback.
  const eProtected = tray.status?.protected ?? false;
  const eInspected = tray.stats?.inspected ?? 0;
  const eDropped = tray.stats?.dropped ?? 0;
  const ePassed = tray.stats?.passed ?? 0;
  const eMemory = tray.stats?.memory ?? 0;
  const eMemoryMb = tray.stats?.memoryMb ?? 0;
  const eSigContrib = tray.stats?.bayanihan?.contributions ?? 0;
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
    lastUpdate: 0, // Not used as much anymore, or can be static
    eProtected,
    eInspected,
    eDropped,
    ePassed,
    eMemory,
    eMemoryMb,
    eSigContrib,
    eLastThreat,
    eLogs,
    detectionLogsContainerRef,
    live,
    tray,
  };
}
