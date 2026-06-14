import React, { useState, useEffect, useRef } from 'react';
import { Shield, Eye, EyeOff, Fingerprint, Scan, KeyRound, ChevronRight, CheckCircle, XCircle, Loader } from 'lucide-react';

type MFAMethod = 'otp' | 'fingerprint' | 'face';
type AuthStep = 'credentials' | 'mfa' | 'verifying' | 'success' | 'failed';

interface LoginPageProps {
  onLogin: () => void;
}

const MOCK_DIGITAL_ID = 'ADM-7734-ALPHA';
const MOCK_PASSWORD = 'SentiNet@2049';
const MOCK_OTP = '482910';

export default function LoginPage({ onLogin }: LoginPageProps) {
  const [digitalId, setDigitalId] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [mfaMethod, setMfaMethod] = useState<MFAMethod>('otp');
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [step, setStep] = useState<AuthStep>('credentials');
  const [credError, setCredError] = useState('');
  const [mfaError, setMfaError] = useState('');
  const [scanProgress, setScanProgress] = useState(0);
  const [scanLabel, setScanLabel] = useState('');
  const [logLines, setLogLines] = useState<string[]>([
    '> SENTINET RELAY NODE v2.4.9 INITIALIZED',
    '> ENCRYPTION LAYER: AES-256-GCM ACTIVE',
    '> BLOCKCHAIN HANDSHAKE: MULTICHAIN OK',
    '> AWAITING ADMIN AUTHENTICATION...',
  ]);
  const otpRefs = useRef<(HTMLInputElement | null)[]>([]);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const lines = [
      '> SCANNING NETWORK TOPOLOGY...',
      '> AGENT ALPHA: HEARTBEAT OK',
      '> AGENT BRAVO: HEARTBEAT OK',
      '> AGENT CHARLIE: HEARTBEAT OK',
      '> AGENT DELTA: HEARTBEAT OK',
      '> THREAT INDEX: NOMINAL',
      '> SESSION TOKEN: PENDING ADMIN INPUT',
    ];
    let i = 0;
    const t = setInterval(() => {
      if (i < lines.length) {
        setLogLines(prev => [...prev, lines[i]]);
        i++;
      } else {
        clearInterval(t);
      }
    }, 800);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: 'smooth' });
  }, [logLines]);

  const handleCredSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (digitalId.trim() === '' || password.trim() === '') {
      setCredError('ALL FIELDS REQUIRED.');
      return;
    }
    if (digitalId !== MOCK_DIGITAL_ID || password !== MOCK_PASSWORD) {
      setCredError('INVALID DIGITAL ID OR PASSWORD. ACCESS DENIED.');
      setLogLines(prev => [...prev, `> AUTH FAILURE: INVALID CREDENTIALS FOR "${digitalId}"`]);
      return;
    }
    setCredError('');
    setLogLines(prev => [...prev, `> CREDENTIALS ACCEPTED FOR "${digitalId}"`, '> INITIATING MFA CHALLENGE...']);
    setStep('mfa');
  };

  const handleOtpChange = (val: string, idx: number) => {
    if (!/^\d?$/.test(val)) return;
    const next = [...otp];
    next[idx] = val;
    setOtp(next);
    if (val && idx < 5) otpRefs.current[idx + 1]?.focus();
  };

  const handleOtpKeyDown = (e: React.KeyboardEvent, idx: number) => {
    if (e.key === 'Backspace' && !otp[idx] && idx > 0) {
      otpRefs.current[idx - 1]?.focus();
    }
  };

  const runScan = (label: string, successMsg: string) => {
    setStep('verifying');
    setScanProgress(0);
    setScanLabel(label);
    let p = 0;
    const scanMsgs = [
      `> ${label} SCAN INITIATED...`,
      `> READING BIOMETRIC SIGNATURE...`,
      `> CROSS-REFERENCING ADMIN REGISTRY...`,
    ];
    let msgIdx = 0;
    const t = setInterval(() => {
      p += Math.floor(Math.random() * 12) + 6;
      if (msgIdx < scanMsgs.length && p > msgIdx * 33) {
        setLogLines(prev => [...prev, scanMsgs[msgIdx]]);
        msgIdx++;
      }
      setScanProgress(Math.min(p, 100));
      if (p >= 100) {
        clearInterval(t);
        setLogLines(prev => [...prev, `> ${successMsg}`, '> SESSION GRANTED. LOADING DASHBOARD...']);
        setTimeout(() => { setStep('success'); setTimeout(onLogin, 1200); }, 400);
      }
    }, 180);
  };

  const handleMfaSubmit = () => {
    setMfaError('');
    if (mfaMethod === 'otp') {
      const entered = otp.join('');
      if (entered.length < 6) { setMfaError('ENTER COMPLETE 6-DIGIT OTP.'); return; }
      if (entered !== MOCK_OTP) {
        setMfaError('INVALID OTP. VERIFICATION FAILED.');
        setLogLines(prev => [...prev, '> OTP MISMATCH — CHALLENGE REJECTED.']);
        return;
      }
      setLogLines(prev => [...prev, '> OTP ACCEPTED.', '> SESSION GRANTED. LOADING DASHBOARD...']);
      setStep('verifying');
      setScanProgress(0);
      setScanLabel('OTP');
      let p = 0;
      const t = setInterval(() => {
        p += 20;
        setScanProgress(Math.min(p, 100));
        if (p >= 100) { clearInterval(t); setStep('success'); setTimeout(onLogin, 1200); }
      }, 120);
    } else if (mfaMethod === 'fingerprint') {
      runScan('FINGERPRINT', 'BIOMETRIC MATCH CONFIRMED — FINGERPRINT');
    } else {
      runScan('FACIAL RECOGNITION', 'BIOMETRIC MATCH CONFIRMED — FACE ID');
    }
  };

  const otpHint = MOCK_OTP;

  return (
    <div className="min-h-screen w-full bg-[#0F172A] flex flex-col font-['Inter',_sans-serif] antialiased">

      {/* Top bar */}
      <header className="flex justify-between items-center bg-[#1E3A8A] border-b-4 border-[#DC2626] px-8 py-4 shrink-0">
        <div className="flex items-center gap-3">
          <Shield className="w-7 h-7 text-white" fill="white" />
          <span className="text-white text-xl font-bold tracking-[0.2em] uppercase">SentiNet — Relay Node Control Hub</span>
        </div>
        <div className="flex items-center gap-3 font-['JetBrains_Mono',_monospace] text-xs text-blue-200">
          <span className="w-2 h-2 bg-[#16A34A] inline-block border border-green-400"></span>
          SYSTEM ONLINE
          <span className="ml-4 text-slate-400">NODE: POC-CTRL-HUB-01</span>
        </div>
      </header>

      <div className="flex flex-1">

        {/* Left — terminal log */}
        <div className="hidden lg:flex w-[420px] shrink-0 flex-col border-r-2 border-[#334155] bg-[#0B1120]">
          <div className="border-b-2 border-[#334155] px-5 py-3 text-xs font-bold uppercase tracking-widest text-[#64748B] font-['JetBrains_Mono',_monospace]">
            // SYSTEM BOOT LOG
          </div>
          <div ref={logRef} className="flex-1 overflow-y-auto p-5 font-['JetBrains_Mono',_monospace] text-xs text-[#22D3EE] leading-6 space-y-0.5">
            {logLines.map((line, i) => (
              <div key={i} className={i === logLines.length - 1 ? 'text-white' : 'text-[#22D3EE] opacity-80'}>{line}</div>
            ))}
            <div className="inline-block w-2 h-4 bg-[#22D3EE] animate-pulse ml-1 align-middle" />
          </div>
          <div className="border-t-2 border-[#334155] p-4 text-[10px] font-['JetBrains_Mono',_monospace] text-[#475569] leading-5">
            <div>ENCRYPTION: AES-256-GCM</div>
            <div>BLOCKCHAIN: MULTICHAIN v2.3</div>
            <div>PROTOCOL: BAYANIHAN SYNC v1.1</div>
          </div>
        </div>

        {/* Center — login form */}
        <div className="flex-1 flex items-center justify-center p-8 bg-[#0F172A]">
          <div className="w-full max-w-[460px]">

            {/* Title block */}
            <div className="border-2 border-[#1E3A8A] bg-[#1E3A8A] p-5 mb-0">
              <div className="text-white font-bold uppercase tracking-[0.15em] text-base">Administrator Authentication</div>
              <div className="text-blue-200 text-xs font-['JetBrains_Mono',_monospace] mt-1 tracking-widest">CLEARANCE LEVEL: OMEGA-5 REQUIRED</div>
            </div>

            <div className="border-2 border-t-0 border-[#334155] bg-[#131E2E] p-8">

              {/* STEP 1 — Credentials */}
              {(step === 'credentials') && (
                <form onSubmit={handleCredSubmit} className="space-y-6">
                  <div>
                    <label className="block text-[#94A3B8] text-xs font-bold uppercase tracking-widest mb-2 font-['JetBrains_Mono',_monospace]">
                      Digital ID
                    </label>
                    <input
                      type="text"
                      value={digitalId}
                      onChange={e => setDigitalId(e.target.value)}
                      placeholder="ADM-XXXX-XXXXX"
                      className="w-full bg-[#0F172A] border-2 border-[#334155] text-white font-['JetBrains_Mono',_monospace] text-sm px-4 py-3 placeholder-[#334155] focus:outline-none focus:border-[#1E3A8A] tracking-widest"
                      autoComplete="off"
                      spellCheck={false}
                    />
                    <div className="text-[10px] text-[#475569] font-['JetBrains_Mono',_monospace] mt-1">HINT: ADM-7734-ALPHA</div>
                  </div>

                  <div>
                    <label className="block text-[#94A3B8] text-xs font-bold uppercase tracking-widest mb-2 font-['JetBrains_Mono',_monospace]">
                      Password
                    </label>
                    <div className="relative">
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        placeholder="••••••••••••••"
                        className="w-full bg-[#0F172A] border-2 border-[#334155] text-white font-['JetBrains_Mono',_monospace] text-sm px-4 py-3 pr-12 placeholder-[#334155] focus:outline-none focus:border-[#1E3A8A]"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(v => !v)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-[#475569] hover:text-[#94A3B8]"
                      >
                        {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                    <div className="text-[10px] text-[#475569] font-['JetBrains_Mono',_monospace] mt-1">HINT: SentiNet@2049</div>
                  </div>

                  {credError && (
                    <div className="flex items-center gap-2 bg-[#7F1D1D] border-2 border-[#DC2626] px-4 py-3 text-[#FCA5A5] text-xs font-bold uppercase tracking-widest font-['JetBrains_Mono',_monospace]">
                      <XCircle className="w-4 h-4 shrink-0" />
                      {credError}
                    </div>
                  )}

                  <button
                    type="submit"
                    className="w-full bg-[#1E3A8A] hover:bg-[#1e40af] border-2 border-[#1E3A8A] text-white font-bold uppercase tracking-[0.2em] py-4 flex items-center justify-center gap-3 text-sm transition-none active:bg-[#172554]"
                  >
                    <ChevronRight className="w-5 h-5" />
                    AUTHENTICATE
                  </button>
                </form>
              )}

              {/* STEP 2 — MFA */}
              {step === 'mfa' && (
                <div className="space-y-6">
                  <div className="text-[#22D3EE] text-xs font-['JetBrains_Mono',_monospace] border-l-4 border-[#22D3EE] pl-3 uppercase tracking-widest">
                    Multi-Factor Authentication Required
                  </div>

                  {/* MFA method selector */}
                  <div className="grid grid-cols-3 gap-2">
                    {([
                      { id: 'otp', label: 'OTP Code', icon: <KeyRound className="w-5 h-5" /> },
                      { id: 'fingerprint', label: 'Fingerprint', icon: <Fingerprint className="w-5 h-5" /> },
                      { id: 'face', label: 'Face ID', icon: <Scan className="w-5 h-5" /> },
                    ] as { id: MFAMethod; label: string; icon: React.ReactNode }[]).map(m => (
                      <button
                        key={m.id}
                        onClick={() => { setMfaMethod(m.id); setMfaError(''); setOtp(['','','','','','']); }}
                        className={`flex flex-col items-center gap-2 py-4 px-2 border-2 text-xs font-bold uppercase tracking-widest transition-none ${
                          mfaMethod === m.id
                            ? 'border-[#1E3A8A] bg-[#1E3A8A] text-white'
                            : 'border-[#334155] bg-[#0F172A] text-[#64748B] hover:border-[#475569] hover:text-[#94A3B8]'
                        }`}
                      >
                        {m.icon}
                        {m.label}
                      </button>
                    ))}
                  </div>

                  {/* OTP input */}
                  {mfaMethod === 'otp' && (
                    <div className="space-y-4">
                      <div className="text-[#94A3B8] text-xs font-['JetBrains_Mono',_monospace] uppercase tracking-widest">
                        Enter 6-digit OTP sent to registered device
                      </div>
                      <div className="flex gap-3 justify-center">
                        {otp.map((d, i) => (
                          <input
                            key={i}
                            ref={el => { otpRefs.current[i] = el; }}
                            type="text"
                            inputMode="numeric"
                            maxLength={1}
                            value={d}
                            onChange={e => handleOtpChange(e.target.value, i)}
                            onKeyDown={e => handleOtpKeyDown(e, i)}
                            className="w-12 h-14 bg-[#0F172A] border-2 border-[#334155] text-white text-center font-['JetBrains_Mono',_monospace] text-xl focus:outline-none focus:border-[#1E3A8A]"
                          />
                        ))}
                      </div>
                      <div className="text-[10px] text-[#475569] font-['JetBrains_Mono',_monospace]">MOCK OTP: {otpHint}</div>
                    </div>
                  )}

                  {/* Fingerprint mock */}
                  {mfaMethod === 'fingerprint' && (
                    <div className="flex flex-col items-center gap-4 py-4">
                      <div className="w-28 h-28 border-2 border-[#334155] bg-[#0F172A] flex items-center justify-center relative">
                        <Fingerprint className="w-16 h-16 text-[#1E3A8A]" />
                        <div className="absolute inset-0 border-2 border-[#22D3EE] opacity-20 animate-ping" />
                      </div>
                      <div className="text-[#94A3B8] text-xs font-['JetBrains_Mono',_monospace] uppercase tracking-widest text-center">
                        Place registered finger on scanner<br />
                        <span className="text-[#475569] text-[10px]">MOCK: click verify to simulate</span>
                      </div>
                    </div>
                  )}

                  {/* Face ID mock */}
                  {mfaMethod === 'face' && (
                    <div className="flex flex-col items-center gap-4 py-4">
                      <div className="w-28 h-28 border-2 border-[#334155] bg-[#0F172A] flex items-center justify-center relative overflow-hidden">
                        <Scan className="w-16 h-16 text-[#1E3A8A]" />
                        {/* scan line animation */}
                        <div className="absolute left-0 right-0 h-0.5 bg-[#22D3EE] opacity-70"
                          style={{ animation: 'scanline 2s linear infinite', top: '0%' }} />
                      </div>
                      <div className="text-[#94A3B8] text-xs font-['JetBrains_Mono',_monospace] uppercase tracking-widest text-center">
                        Look directly at the camera<br />
                        <span className="text-[#475569] text-[10px]">MOCK: click verify to simulate</span>
                      </div>
                    </div>
                  )}

                  {mfaError && (
                    <div className="flex items-center gap-2 bg-[#7F1D1D] border-2 border-[#DC2626] px-4 py-3 text-[#FCA5A5] text-xs font-bold uppercase tracking-widest font-['JetBrains_Mono',_monospace]">
                      <XCircle className="w-4 h-4 shrink-0" />
                      {mfaError}
                    </div>
                  )}

                  <button
                    onClick={handleMfaSubmit}
                    className="w-full bg-[#1E3A8A] hover:bg-[#1e40af] border-2 border-[#1E3A8A] text-white font-bold uppercase tracking-[0.2em] py-4 flex items-center justify-center gap-3 text-sm transition-none active:bg-[#172554]"
                  >
                    <Shield className="w-5 h-5" />
                    VERIFY &amp; ENTER
                  </button>

                  <button
                    onClick={() => { setStep('credentials'); setCredError(''); setMfaError(''); }}
                    className="w-full text-[#475569] text-xs uppercase tracking-widest font-['JetBrains_Mono',_monospace] hover:text-[#94A3B8] py-2"
                  >
                    ← Back to Credentials
                  </button>
                </div>
              )}

              {/* STEP 3 — Verifying */}
              {step === 'verifying' && (
                <div className="space-y-6 py-4">
                  <div className="flex items-center gap-3 text-[#22D3EE] font-['JetBrains_Mono',_monospace] text-sm uppercase tracking-widest">
                    <Loader className="w-5 h-5 animate-spin" />
                    VERIFYING {scanLabel}...
                  </div>
                  <div className="w-full h-6 border-2 border-[#334155] bg-[#0F172A] p-1">
                    <div
                      className="h-full bg-[#1E3A8A] transition-all duration-200"
                      style={{ width: `${scanProgress}%` }}
                    />
                  </div>
                  <div className="text-right text-xs font-['JetBrains_Mono',_monospace] text-[#475569]">{scanProgress}%</div>
                </div>
              )}

              {/* STEP 4 — Success */}
              {step === 'success' && (
                <div className="space-y-4 py-6 flex flex-col items-center text-center">
                  <CheckCircle className="w-14 h-14 text-[#16A34A]" />
                  <div className="text-white font-bold uppercase tracking-widest text-base">ACCESS GRANTED</div>
                  <div className="text-[#16A34A] font-['JetBrains_Mono',_monospace] text-xs uppercase tracking-widest">Loading dashboard...</div>
                </div>
              )}

            </div>

            {/* Footer strip */}
            <div className="border-2 border-t-0 border-[#334155] bg-[#0B1120] px-5 py-3 flex justify-between items-center">
              <span className="text-[#334155] text-[10px] font-['JetBrains_Mono',_monospace] uppercase tracking-widest">CLASSIFIED // AUTHORIZED USE ONLY</span>
              <span className="text-[#334155] text-[10px] font-['JetBrains_Mono',_monospace]">POC-v2.4.9</span>
            </div>
          </div>
        </div>

        {/* Right — security status panel */}
        <div className="hidden xl:flex w-[240px] shrink-0 flex-col border-l-2 border-[#334155] bg-[#0B1120]">
          <div className="border-b-2 border-[#334155] px-5 py-3 text-xs font-bold uppercase tracking-widest text-[#64748B] font-['JetBrains_Mono',_monospace]">
            // SEC STATUS
          </div>
          <div className="flex-1 p-5 space-y-5 font-['JetBrains_Mono',_monospace] text-xs">
            {[
              { label: 'FIREWALL', status: 'ACTIVE', ok: true },
              { label: 'IDS ENGINE', status: 'RUNNING', ok: true },
              { label: 'CHAIN SYNC', status: 'IN SYNC', ok: true },
              { label: 'VPN TUNNEL', status: 'ESTABLISHED', ok: true },
              { label: 'THREAT FEED', status: 'NOMINAL', ok: true },
              { label: 'ROGUE AP', status: '0 DETECTED', ok: true },
            ].map(item => (
              <div key={item.label} className="flex justify-between items-center border-b border-[#1E293B] pb-3">
                <span className="text-[#475569] uppercase tracking-widest">{item.label}</span>
                <span className={`text-[10px] font-bold ${item.ok ? 'text-[#16A34A]' : 'text-[#DC2626]'}`}>{item.status}</span>
              </div>
            ))}
          </div>
          <div className="border-t-2 border-[#334155] p-5">
            <div className="text-[#DC2626] text-[10px] uppercase tracking-widest font-bold mb-1">LAST BREACH ATTEMPT</div>
            <div className="text-[#475569] text-[10px]">14:02:37 — IP 10.0.0.99</div>
            <div className="text-[#475569] text-[10px]">ARP SPOOF — BLOCKED</div>
          </div>
        </div>

      </div>

      <style>{`
        @keyframes scanline {
          0% { top: 0%; }
          100% { top: 100%; }
        }
      `}</style>
    </div>
  );
}
