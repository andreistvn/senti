import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router';
import { Shield, Eye, EyeOff, ChevronRight } from 'lucide-react';

const BOOT_LINES = [
  { text: '> SENTINET RELAY NODE v2.4.9 INITIALIZED', delay: 0 },
  { text: '> ENCRYPTION LAYER: AES-256-GCM ACTIVE', delay: 300 },
  { text: '> BLOCKCHAIN HANDSHAKE: MULTICHAIN OK', delay: 600 },
  { text: '> AWAITING ADMIN AUTHENTICATION...', delay: 900 },
  { text: '> SCANNING NETWORK TOPOLOGY...', delay: 1200 },
  { text: '> AGENT BRAVO: HEARTBEAT OK', delay: 1500 },
  { text: '> AGENT CHARLIE: HEARTBEAT OK', delay: 1800 },
  { text: '> AGENT DELTA: HEARTBEAT OK', delay: 2100 },
  { text: '> THREAT INDEX: NOMINAL', delay: 2400 },
  { text: '> SESSION TOKEN: PENDING ADMIN INPUT', delay: 2700 },
];

const SEC_STATUS = [
  { label: 'FIREWALL', value: 'ACTIVE', ok: true },
  { label: 'IDS ENGINE', value: 'RUNNING', ok: true },
  { label: 'CHAIN SYNC', value: 'IN SYNC', ok: true },
  { label: 'VPN TUNNEL', value: 'ESTABLISHED', ok: true },
  { label: 'THREAT FEED', value: 'NOMINAL', ok: true },
  { label: 'ROGUE AP', value: '0 DETECTED', ok: true },
];

export default function Login() {
  const navigate = useNavigate();
  const [digitalId, setDigitalId] = useState('');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [visibleLines, setVisibleLines] = useState(0);
  const [cursor, setCursor] = useState(true);

  useEffect(() => {
    BOOT_LINES.forEach((line, i) => {
      setTimeout(() => setVisibleLines(i + 1), line.delay);
    });
    const cursorInterval = setInterval(() => setCursor(c => !c), 530);
    return () => clearInterval(cursorInterval);
  }, []);

  function handleLogin() {
    if (!digitalId.trim() || !password) return;
    navigate('/dashboard');
  }

  return (
    <div className="min-h-screen bg-[#080d1a] flex flex-col">

      {/* Header */}
      <header className="bg-[#0d1b3e] border-b-2 border-[#c0392b] px-6 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <Shield className="w-5 h-5 text-white" strokeWidth={2} />
          <span className="text-white tracking-widest text-sm font-bold uppercase">SENTINET — RELAY NODE CONTROL HUB</span>
        </div>
        <div className="flex items-center gap-6 text-xs">
          <span className="flex items-center gap-2 text-[#00ff88]">
            <span className="w-2 h-2 rounded-full bg-[#00ff88] inline-block"></span>
            SYSTEM ONLINE
          </span>
          <span className="text-[#8899bb]">NODE: POC-CTRL-HUB-01</span>
        </div>
      </header>

      {/* Three-panel body */}
      <div className="flex flex-1 overflow-hidden">

        {/* LEFT — System Boot Log */}
        <div className="w-80 shrink-0 border-r border-[#1e3a5f] p-5 overflow-y-auto">
          <p className="text-[#8899bb] text-xs mb-4 tracking-widest">// SYSTEM BOOT LOG</p>
          <div className="space-y-1.5">
            {BOOT_LINES.slice(0, visibleLines).map((line, i) => (
              <p key={i} className="text-[#00ccaa] text-xs leading-relaxed font-mono">{line.text}</p>
            ))}
            {visibleLines < BOOT_LINES.length && (
              <span className={`inline-block w-2 h-4 bg-[#00ccaa] ${cursor ? 'opacity-100' : 'opacity-0'} transition-opacity`} />
            )}
            {visibleLines >= BOOT_LINES.length && (
              <span className={`inline-block w-2 h-4 bg-[#00ccaa] ${cursor ? 'opacity-100' : 'opacity-0'} transition-opacity`} />
            )}
          </div>
          <div className="absolute bottom-6 left-5 text-[10px] text-[#3a5070] space-y-0.5 font-mono">
            <p>ENCRYPTION: AES-256-GCM</p>
            <p>BLOCKCHAIN: MULTICHAIN v2.3</p>
            <p>PROTOCOL: BAYANIHAN SYNC v1.1</p>
          </div>
        </div>

        {/* CENTER — Auth Modal */}
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="w-full max-w-md border border-[#2a4a7f] bg-[#0d1b3e]">

            {/* Modal header */}
            <div className="bg-[#1a2f5e] border-b border-[#2a4a7f] px-6 py-4">
              <h1 className="text-white tracking-[0.2em] text-base font-bold uppercase">Administrator Authentication</h1>
              <p className="text-[#00ccaa] text-xs tracking-widest mt-1">CLEARANCE LEVEL: OMEGA-5 REQUIRED</p>
            </div>

            {/* Modal body */}
            <div className="px-6 py-6 space-y-5">
              <div>
                <label className="text-[#8899bb] text-xs tracking-widest block mb-2">DIGITAL ID</label>
                <input
                  className="w-full bg-[#060b15] border border-[#2a4a7f] text-[#00ccaa] placeholder-[#2a4a7f] px-4 py-3 text-sm outline-none focus:border-[#00ccaa] transition tracking-widest font-mono"
                  placeholder="ADM-XXXX-XXXXX"
                  value={digitalId}
                  onChange={e => setDigitalId(e.target.value)}
                />
                <p className="text-[#3a5070] text-[10px] mt-1 tracking-wider">HINT: SNET-XXXX-XXXXXX-XXXXX</p>
              </div>

              <div>
                <label className="text-[#8899bb] text-xs tracking-widest block mb-2">PASSWORD</label>
                <div className="relative">
                  <input
                    type={showPass ? 'text' : 'password'}
                    className="w-full bg-[#060b15] border border-[#2a4a7f] text-[#00ccaa] placeholder-[#2a4a7f] px-4 py-3 text-sm pr-10 outline-none focus:border-[#00ccaa] transition tracking-widest font-mono"
                    placeholder="••••••••••••••"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleLogin()}
                  />
                  <button onClick={() => setShowPass(!showPass)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#3a5070] hover:text-[#8899bb] transition">
                    {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-[#3a5070] text-[10px] mt-1 tracking-wider">HINT: SentiNet@2049</p>
              </div>

              <button
                onClick={handleLogin}
                disabled={!digitalId.trim() || !password}
                className="w-full bg-[#1a4fd6] hover:bg-[#2962ff] disabled:opacity-30 disabled:cursor-not-allowed text-white tracking-[0.3em] text-sm py-4 flex items-center justify-center gap-3 transition uppercase font-bold"
              >
                <ChevronRight className="w-4 h-4" strokeWidth={3} />
                AUTHENTICATE
              </button>
            </div>

            {/* Modal footer */}
            <div className="border-t border-[#2a4a7f] px-6 py-3 flex items-center justify-between">
              <span className="text-[#3a5070] text-[10px] tracking-widest">CLASSIFIED // AUTHORIZED USE ONLY</span>
              <span className="text-[#3a5070] text-[10px] tracking-widest">POC-v2.6.9</span>
            </div>
          </div>

          <p className="absolute bottom-8 text-[#3a5070] text-xs tracking-wider">
            NO ACCOUNT? <button onClick={() => navigate('/')} className="text-[#00ccaa] hover:text-white transition">REGISTER HERE</button>
          </p>
        </div>

        {/* RIGHT — SEC STATUS */}
        <div className="w-72 shrink-0 border-l border-[#1e3a5f] p-5">
          <p className="text-[#8899bb] text-xs mb-5 tracking-widest">// SEC STATUS</p>
          <div className="space-y-4">
            {SEC_STATUS.map(item => (
              <div key={item.label} className="flex items-center justify-between border-b border-[#1e3a5f] pb-3">
                <span className="text-[#8899bb] text-xs tracking-widest">{item.label}</span>
                <span className={`text-xs tracking-widest font-bold ${item.ok ? 'text-[#00ff88]' : 'text-[#ff3b3b]'}`}>{item.value}</span>
              </div>
            ))}
          </div>

          {/* Last breach */}
          <div className="mt-auto pt-8">
            <p className="text-[#ff3b3b] text-[10px] tracking-widest mb-1">LAST BREACH ATTEMPT</p>
            <p className="text-[#ff3b3b] text-[10px]">14:02:37 — IP 10.0.0.99</p>
            <p className="text-[#ff3b3b] text-[10px]">ARP SPOOF — BLOCKED</p>
          </div>
        </div>

      </div>
    </div>
  );
}
