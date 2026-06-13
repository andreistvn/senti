import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router';
import * as Switch from '@radix-ui/react-switch';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import {
  Shield, ShieldCheck, ShieldAlert, Activity,
  Settings, HelpCircle, LogOut, Radio, Wifi
} from 'lucide-react';
import { toast } from 'sonner';

function randomMac() {
  return Array.from({ length: 6 }, () =>
    Math.floor(Math.random() * 256).toString(16).padStart(2, '0').toUpperCase()
  ).join(':');
}

interface AgentToggleProps {
  onOpenDashboard?: () => void;
}

export default function AgentToggle({ onOpenDashboard }: AgentToggleProps) {
  const navigate = useNavigate();
  const [isActive, setIsActive] = useState(false);
  const [forceLocal, setForceLocal] = useState(false);
  const [packetCount, setPacketCount] = useState(0);
  const [blockedCount, setBlockedCount] = useState(0);

  const state = isActive ? (forceLocal ? 'local' : 'active') : 'disabled';

  const THREAT_LABELS = [
    'ARP Spoofing packet',
    'MITM attempt',
    'Malicious ARP reply',
    'Rogue gateway probe',
    'ARP cache poisoning',
  ];

  useEffect(() => {
    if (!isActive) return;
    const t = setInterval(() => {
      setPacketCount(p => p + Math.floor(Math.random() * 12 + 3));
      if (Math.random() > 0.85) {
        setBlockedCount(b => {
          const next = b + 1;
          const label = THREAT_LABELS[next % THREAT_LABELS.length];
          toast(`SentiNet blocked a ${label}`, {
            description: `From MAC ${randomMac()} · Tier-${Math.random() > 0.5 ? 1 : 2} detection`,
            duration: 4500,
            icon: '🛡️',
          });
          return next;
        });
      }
    }, 800);
    return () => clearInterval(t);
  }, [isActive]);

  const stateColor = state === 'active' ? '#00cc66' : state === 'local' ? '#f59e0b' : '#3a5070';
  const stateBg    = state === 'active' ? '#00cc6615' : state === 'local' ? '#f59e0b15' : 'transparent';
  const stateBorder= state === 'active' ? '#00cc6640' : state === 'local' ? '#f59e0b40' : '#1e3a5f';

  return (
    /* Full-page centering wrapper */
    <div className="min-h-screen bg-[#060a14] flex items-center justify-center">

      {/* Extension popup shell — fixed 340×480 */}
      <div
        className="flex flex-col overflow-hidden shadow-2xl"
        style={{
          width: 340,
          height: 480,
          background: '#0b1120',
          border: '1px solid #1e3a5f',
          boxShadow: '0 0 0 1px #0d1b3e, 0 24px 64px rgba(0,0,0,0.7)',
        }}
      >

        {/* ── Title bar ── */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#1e3a5f] bg-[#0d1b3e] shrink-0">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-[#00ccaa]" strokeWidth={2} />
            <span className="text-white text-xs font-semibold tracking-wider">SentiNet Agent</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[#8899bb] text-[10px] tracking-wider">DICT Wi-Fi</span>
            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <button className="text-[#8899bb] hover:text-white transition p-0.5 outline-none">
                  <Settings className="w-3.5 h-3.5" />
                </button>
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content
                  className="min-w-[160px] bg-[#0d1b3e] border border-[#2a4a7f] py-1 z-50 text-[11px]"
                  sideOffset={6} align="end"
                >
                  <DropdownMenu.Item className="flex items-center gap-2 px-3 py-2 text-[#8899bb] hover:bg-[#1a2f5e] hover:text-white cursor-pointer outline-none transition">
                    <Settings className="w-3 h-3" /> Settings
                  </DropdownMenu.Item>
                  <DropdownMenu.Item className="flex items-center gap-2 px-3 py-2 text-[#8899bb] hover:bg-[#1a2f5e] hover:text-white cursor-pointer outline-none transition">
                    <HelpCircle className="w-3 h-3" /> Help
                  </DropdownMenu.Item>
                  <DropdownMenu.Separator className="h-px bg-[#1e3a5f] my-1" />
                  <DropdownMenu.Item className="flex items-center gap-2 px-3 py-2 text-[#ff3b3b] hover:bg-[#ff3b3b]/10 cursor-pointer outline-none transition">
                    <LogOut className="w-3 h-3" /> Exit
                  </DropdownMenu.Item>
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
          </div>
        </div>

        {/* ── Body ── */}
        <div className="flex-1 flex flex-col items-center justify-between px-5 py-5">

          {/* Logo + network */}
          <div className="text-center w-full">
            <div
              className="text-2xl font-bold tracking-[0.25em] select-none cursor-default"
              style={{
                background: isActive
                  ? 'linear-gradient(90deg,#00ccaa,#1a4fd6)'
                  : 'linear-gradient(90deg,#2a4a7f,#1e3a5f)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}
              onDoubleClick={() => setForceLocal(f => !f)}
            >
              SENTINET
            </div>
            <div className="flex items-center justify-center gap-1.5 mt-1.5">
              <Wifi className="w-3 h-3 text-[#3a5070]" strokeWidth={2} />
              <span className="text-[#3a5070] text-[10px] tracking-widest font-mono">DICT PUBLIC WI-FI</span>
            </div>
          </div>

          {/* Toggle + status pill */}
          <div className="flex flex-col items-center gap-4">
            {/* Glow ring */}
            <div
              className="rounded-full p-1 transition-all duration-500"
              style={{
                boxShadow: isActive ? `0 0 28px 6px ${stateColor}33` : 'none',
                background: stateBg,
                border: `1px solid ${stateBorder}`,
              }}
            >
              <Switch.Root
                checked={isActive}
                onCheckedChange={setIsActive}
                className="relative outline-none"
                style={{
                  width: 72,
                  height: 40,
                  background: isActive ? `${stateColor}22` : '#0d1b3e',
                  border: `1.5px solid ${isActive ? stateColor : '#2a4a7f'}`,
                  borderRadius: 20,
                  display: 'flex',
                  alignItems: 'center',
                  padding: '0 4px',
                  transition: 'all 0.3s',
                }}
              >
                <Switch.Thumb
                  className="flex items-center justify-center transition-transform duration-300"
                  style={{
                    width: 30,
                    height: 30,
                    borderRadius: '50%',
                    background: '#0d1b3e',
                    border: `1.5px solid ${isActive ? stateColor : '#2a4a7f'}`,
                    transform: isActive ? 'translateX(32px)' : 'translateX(0)',
                    boxShadow: isActive ? `0 0 10px ${stateColor}88` : 'none',
                  }}
                >
                  {state === 'active'   && <ShieldCheck className="w-3.5 h-3.5" style={{ color: stateColor }} strokeWidth={2.5} />}
                  {state === 'local'    && <ShieldAlert  className="w-3.5 h-3.5" style={{ color: stateColor }} strokeWidth={2.5} />}
                  {state === 'disabled' && <Shield       className="w-3.5 h-3.5 text-[#3a5070]" strokeWidth={1.5} />}
                </Switch.Thumb>
              </Switch.Root>
            </div>

            {/* Status label */}
            <div className="text-center">
              <p
                className="text-sm font-semibold tracking-widest uppercase"
                style={{ color: stateColor }}
              >
                {state === 'active'   && 'Protected'}
                {state === 'local'    && 'Local Only'}
                {state === 'disabled' && 'Unprotected'}
              </p>
              <p className="text-[#8899bb] text-[10px] tracking-wide mt-1 leading-relaxed">
                {state === 'active'   && 'Blocking MITM & ARP spoofing'}
                {state === 'local'    && 'Relay offline — local only'}
                {state === 'disabled' && 'Enable protection to secure\nyour public Wi-Fi session'}
              </p>
            </div>
          </div>

          {/* Stats row */}
          <div
            className="w-full grid grid-cols-3 border border-[#1e3a5f]"
            style={{ background: '#060a14' }}
          >
            {[
              { label: 'Inspected', value: packetCount.toLocaleString(), color: '#00ccaa' },
              { label: 'Blocked',   value: blockedCount.toString(),      color: '#ff3b3b' },
              { label: 'Relay',     value: isActive ? 'Online' : 'Offline', color: isActive ? '#00cc66' : '#3a5070' },
            ].map((stat, i) => (
              <div
                key={stat.label}
                className={`flex flex-col items-center py-2.5 gap-0.5 ${i < 2 ? 'border-r border-[#1e3a5f]' : ''}`}
              >
                <span className="font-mono text-sm font-semibold" style={{ color: stat.color }}>{stat.value}</span>
                <span className="text-[#3a5070] text-[9px] tracking-wider uppercase">{stat.label}</span>
              </div>
            ))}
          </div>

          {/* Module statuses */}
          <div className="w-full space-y-1.5">
            {[
              { label: 'ARP Guard',   active: 'Active',      inactive: 'Inactive' },
              { label: 'MITM Filter', active: 'Running',     inactive: 'Offline'  },
              { label: 'Chain Sync',  active: 'In Sync',     inactive: 'Paused'   },
            ].map(item => (
              <div key={item.label} className="flex items-center justify-between">
                <span className="text-[#8899bb] text-[10px] tracking-wide">{item.label}</span>
                <span
                  className="text-[10px] font-semibold tracking-wider font-mono"
                  style={{ color: isActive ? '#00cc66' : '#3a5070' }}
                >
                  {isActive ? item.active : item.inactive}
                </span>
              </div>
            ))}
          </div>

          {/* Dashboard button */}
          <button
            onClick={() => {
              if (onOpenDashboard) {
                onOpenDashboard();
              } else {
                navigate('/dashboard');
              }
            }}
            className="w-full flex items-center justify-center gap-2 py-2.5 text-[11px] tracking-widest uppercase transition"
            style={{
              background: 'transparent',
              border: '1px solid #1a4fd6',
              color: '#1a4fd6',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = '#1a4fd620'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent'; }}
          >
            <Activity className="w-3.5 h-3.5" /> Open Agent Dashboard
          </button>

        </div>

        {/* ── Footer ── */}
        <div className="flex items-center justify-between px-4 py-2 border-t border-[#1e3a5f] bg-[#060a14] shrink-0">
          <span className="text-[#1e3a5f] text-[9px] font-mono tracking-wider">AES-256-GCM · MULTICHAIN v2.3</span>
          <span className="text-[#1e3a5f] text-[9px] font-mono">v2.4.9</span>
        </div>

      </div>
    </div>
  );
}
