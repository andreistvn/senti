import { useCallback, useEffect, useRef, useState } from 'react';
import {
  getStatus, getStats, getHealth, getEvents, toggle as toggleApi,
  type TrayStatus, type TrayStats, type TrayService, type TrayEvent,
} from '../lib/trayClient';

export interface TrayConnection {
  connected: boolean;
  status: TrayStatus | null;
  stats: TrayStats | null;
  services: TrayService[] | null;
  events: TrayEvent[] | null;
  toggle: () => Promise<void>;
}

/**
 * Polls the local tray daemon every `intervalMs`. While reachable, exposes live
 * status/stats/services/events and `connected = true`. On any failure (tray not
 * running) it flips to `connected = false` so the dashboard can fall back to its
 * own mock data. Safe to use inside Figma Make — failed fetches are swallowed.
 */
export function useTrayConnection(intervalMs = 2000): TrayConnection {
  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState<TrayStatus | null>(null);
  const [stats, setStats] = useState<TrayStats | null>(null);
  const [services, setServices] = useState<TrayService[] | null>(null);
  const [events, setEvents] = useState<TrayEvent[] | null>(null);
  const alive = useRef(true);

  const poll = useCallback(async () => {
    try {
      const [st, stt, hl, ev] = await Promise.all([
        getStatus(), getStats(), getHealth(), getEvents(),
      ]);
      if (!alive.current) return;
      setStatus(st);
      setStats(stt);
      setServices(hl);
      setEvents(ev);
      setConnected(true);
    } catch {
      if (!alive.current) return;
      setConnected(false);
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    poll();
    const id = setInterval(poll, intervalMs);
    return () => {
      alive.current = false;
      clearInterval(id);
    };
  }, [poll, intervalMs]);

  const toggle = useCallback(async () => {
    try {
      const next = await toggleApi();
      setStatus(next);
      setConnected(true);
      poll();
    } catch {
      setConnected(false);
    }
  }, [poll]);

  return { connected, status, stats, services, events, toggle };
}
