import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useTrayConnection } from '../hooks/useTrayConnection';

export type Tab = 'dashboard' | 'diagnostics';

export interface DaemonService {
  id: string;
  name: string;
  status: 'active' | 'loaded' | 'connected' | 'degraded' | 'offline';
  detail: string;
  uptime: string;
}

interface DetectionLog {
  id: number;
  timestamp: string;
  sourceMac: string;
  attackType: string;
  tier: string;
  action: string;
}

const OFFLINE_DAEMONS: DaemonService[] = [
  { id: 'scapy', name: 'Scapy Sniffer', status: 'offline', detail: 'Daemon unreachable', uptime: '0s' },
  { id: 'ml', name: 'Tier-2 ML Engine', status: 'offline', detail: 'Daemon unreachable', uptime: '0s' },
  { id: 'ws', name: 'WebSocket Relay', status: 'offline', detail: 'Daemon unreachable', uptime: '0s' },
  { id: 'arp', name: 'ARP Guard Module', status: 'offline', detail: 'Daemon unreachable', uptime: '0s' },
  { id: 'bayanihan', name: 'Bayanihan Agent', status: 'offline', detail: 'Daemon unreachable', uptime: '0s' },
];

function statusColor(s: DaemonService['status']) {
  return s === 'active' || s === 'loaded' || s === 'connected' ? '#00aa55' : s === 'degraded' ? '#f59e0b' : '#c0392b';
}

function statusLabel(s: DaemonService['status']) {
  return ({ active: 'ACTIVE', loaded: 'LOADED', connected: 'CONNECTED', degraded: 'DEGRADED', offline: 'OFFLINE' }[s]);
}

export function useDashboardState(intervalMs = 2000) {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');
  const [cpuData, setCpuData] = useState(
    Array.from({ length: 60 }, (_, i) => ({ time: i, usage: 0 }))
  );
  
  // Removed mock states (inspected, dropped, passed, daemons, etc.)
  const [restarting, setRestarting] = useState<string | null>(null);

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
  const eUsersProtected = tray.stats?.bayanihan?.usersProtected ?? 0;
  const eLastThreat = tray.stats?.lastThreat ?? null;
  const eDaemons = (live && tray.services) ? tray.services : OFFLINE_DAEMONS;
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

  function restartDaemon(id: string) {
    // Mock restart logic removed. Real restart requires IPC commands which aren't fully hooked up.
    setRestarting(id);
    setTimeout(() => setRestarting(null), 1000);
  }

  return {
    activeTab,
    setActiveTab,
    cpuData,
    lastUpdate: 0, // Not used as much anymore, or can be static
    eProtected,
    eInspected,
    eDropped,
    ePassed,
    eMemory,
    eMemoryMb,
    eSigContrib,
    eUsersProtected,
    eLastThreat,
    eDaemons,
    eLogs,
    detectionLogsContainerRef,
    restarting,
    restartDaemon,
    statusColor,
    statusLabel,
    live,
    tray,
  };
}
