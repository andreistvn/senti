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

const INITIAL_DAEMONS: DaemonService[] = [
  { id: 'scapy', name: 'Scapy Sniffer', status: 'active', detail: 'Capturing ARP frames on wlan0', uptime: '4h 23m' },
  { id: 'ml', name: 'Tier-2 ML Engine', status: 'loaded', detail: 'RandomForest model v3.1 in memory', uptime: '4h 23m' },
  { id: 'ws', name: 'WebSocket Relay', status: 'connected', detail: 'relay.dict.gov.ph:8443 · 12ms ping', uptime: '4h 21m' },
  { id: 'arp', name: 'ARP Guard Module', status: 'active', detail: 'Monitoring 34 active hosts', uptime: '4h 23m' },
  { id: 'bayanihan', name: 'Bayanihan Agent', status: 'connected', detail: 'Peer mesh: 40 nodes reachable', uptime: '4h 18m' },
];

const DETECTION_LOGS: DetectionLog[] = [
  { id: 1, timestamp: '2026-06-10 14:32:18', sourceMac: 'A4:5E:60:E2:3B:1C', attackType: 'ARP Spoofing', tier: 'Tier 1', action: 'Blocked' },
  { id: 2, timestamp: '2026-06-10 14:31:45', sourceMac: 'B8:27:EB:4F:92:D3', attackType: 'ARP Spoofing', tier: 'Tier 2', action: 'Dropped' },
  { id: 3, timestamp: '2026-06-10 14:29:12', sourceMac: '00:1A:7D:DA:71:13', attackType: 'ARP Spoofing', tier: 'Tier 1', action: 'Blocked' },
  { id: 4, timestamp: '2026-06-10 14:27:08', sourceMac: 'DC:A6:32:1F:E8:9A', attackType: 'ARP Spoofing', tier: 'Tier 1', action: 'Blocked' },
  { id: 5, timestamp: '2026-06-10 14:25:33', sourceMac: '2C:F0:5D:8B:42:A7', attackType: 'ARP Spoofing', tier: 'Tier 2', action: 'Dropped' },
  { id: 6, timestamp: '2026-06-10 14:23:51', sourceMac: 'F4:5C:89:C3:2D:6E', attackType: 'ARP Spoofing', tier: 'Tier 1', action: 'Blocked' },
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
    Array.from({ length: 60 }, (_, i) => ({ time: i, usage: Math.random() * 15 + 2 }))
  );
  const [memoryUsage, setMemoryUsage] = useState(84);
  const [lastUpdate, setLastUpdate] = useState(3);
  const [inspected, setInspected] = useState(1247);
  const [dropped, setDropped] = useState(23);
  const [passed, setPassed] = useState(1224);
  const [sigContributions, setSigContributions] = useState(15);
  const [usersProtected, setUsersProtected] = useState(40);
  const [daemons, setDaemons] = useState<DaemonService[]>(INITIAL_DAEMONS);
  const [restarting, setRestarting] = useState<string | null>(null);

  const tray = useTrayConnection(intervalMs);
  const live = tray.connected;
  const liveCpu = tray.stats?.cpu;

  useEffect(() => {
    const interval = setInterval(() => {
      if (live) {
        setCpuData(prev => [
          ...prev.slice(1),
          { time: prev[prev.length - 1].time + 1, usage: liveCpu ?? prev[prev.length - 1].usage },
        ]);
        return;
      }

      setCpuData(prev => [
        ...prev.slice(1),
        { time: prev[prev.length - 1].time + 1, usage: Math.random() * 15 + 2 },
      ]);
      setMemoryUsage(Math.floor(Math.random() * 30 + 70));
      setLastUpdate(Math.floor(Math.random() * 10) + 1);
      setInspected(p => p + Math.floor(Math.random() * 10 + 2));
      setDropped(p => (Math.random() > 0.7 ? p + 1 : p));
      setPassed(p => p + Math.floor(Math.random() * 9 + 2));
      if (Math.random() > 0.92) {
        setSigContributions(c => c + 1);
        setUsersProtected(u => u + Math.floor(Math.random() * 3));
      }
    }, intervalMs);

    return () => clearInterval(interval);
  }, [live, liveCpu, intervalMs]);

  const eProtected = live ? (tray.status?.protected ?? false) : true;
  const eInspected = live ? (tray.stats?.inspected ?? 0) : inspected;
  const eDropped = live ? (tray.stats?.dropped ?? 0) : dropped;
  const ePassed = live ? (tray.stats?.passed ?? 0) : passed;
  const eMemory = live ? (tray.stats?.memory ?? 0) : memoryUsage;
  const eSigContrib = live ? (tray.stats?.bayanihan.contributions ?? 0) : sigContributions;
  const eUsersProtected = live ? (tray.stats?.bayanihan.usersProtected ?? 0) : usersProtected;
  const eLastThreat = live
    ? tray.stats?.lastThreat ?? null
    : { attackType: 'ARP Spoofing', sourceMac: 'A4:5E:60:E2:3B:1C', timestamp: '2 minutes ago' };
  const eDaemons = live && tray.services ? tray.services : daemons;
  const eLogs = live && tray.events && tray.events.length ? tray.events : DETECTION_LOGS;

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
    setRestarting(id);
    setDaemons(prev => prev.map(d => (d.id === id ? { ...d, status: 'degraded' as const, detail: 'Restarting…', uptime: '0s' } : d)));
    setTimeout(() => {
      setDaemons(prev => prev.map(d => {
        if (d.id !== id) return d;
        const original = INITIAL_DAEMONS.find(x => x.id === id)!;
        return { ...original, uptime: '0m 4s' };
      }));
      setRestarting(null);
    }, 2200);
  }

  return {
    activeTab,
    setActiveTab,
    cpuData,
    lastUpdate,
    eProtected,
    eInspected,
    eDropped,
    ePassed,
    eMemory,
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