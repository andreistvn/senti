import React, { useState, useEffect, useContext } from 'react';
import { useNavigate } from 'react-router';
import { Shield, Eye, EyeOff, Copy, Check, ChevronRight, Fingerprint, Lock, Key, AlertTriangle, Scan, ScanFace } from 'lucide-react';
import { AuthContext } from '../App';

export interface RegisteredUser {
  digitalId: string;
  address: string;
  name: string;
}

function generateBlockchainAddress(): string {
  const chars = '0123456789abcdef';
  let addr = '0x';
  for (let i = 0; i < 40; i++) addr += chars[Math.floor(Math.random() * 16)];
  return addr;
}

function generateDigitalId(name: string, address: string): string {
  const timestamp = Date.now().toString(36).toUpperCase();
  const namePart = name.replace(/\s+/g, '').substring(0, 4).toUpperCase().padEnd(4, 'X');
  const addrPart = address.substring(2, 8).toUpperCase();
  return `SNET-${namePart}-${addrPart}-${timestamp}`;
}

function generateSecretPhrase(): string[] {
  const wordlist = [
    'abandon','ability','able','about','above','absent','absorb','abstract','absurd','abuse',
    'access','accident','account','accuse','achieve','acid','acoustic','acquire','across','act',
    'action','actor','actress','actual','adapt','add','addict','address','adjust','admit',
    'adult','advance','advice','aerobic','afford','afraid','again','age','agent','agree',
    'ahead','aim','air','airport','aisle','alarm','album','alcohol','alert','alien',
    'alley','allow','almost','alone','alpha','already','also','alter','always','amateur',
    'amazing','among','amount','amused','analyst','anchor','ancient','anger','angle','angry',
    'animal','ankle','announce','annual','another','answer','antenna','antique','anxiety','apart',
    'april','arch','arctic','area','arena','argue','arm','armed','armor','army',
    'around','arrange','arrest','arrive','arrow','art','artefact','artist','artwork','ask',
  ];
  const phrase: string[] = [];
  const used = new Set<number>();
  while (phrase.length < 12) {
    const idx = Math.floor(Math.random() * wordlist.length);
    if (!used.has(idx)) { used.add(idx); phrase.push(wordlist[idx]); }
  }
  return phrase;
}

function generateTOTPCode(): string {
  return String(Math.floor(100000 + Math.random() * 900000));
}

type Step = 'identity' | 'secret-phrase' | 'mfa-setup' | 'mfa-verify' | 'digital-id';
type MFAMethod = 'totp' | 'face' | 'fingerprint';

const STEP_LABELS = ['IDENTITY', 'SECRET PHRASE', 'MFA SETUP', 'VERIFY', 'DIGITAL ID'];
const STEPS: Step[] = ['identity', 'secret-phrase', 'mfa-setup', 'mfa-verify', 'digital-id'];

export default function Register() {
  const navigate = useNavigate();
  const { setRegisteredUser } = useContext(AuthContext);
  const [step, setStep] = useState<Step>('identity');
  const stepIdx = STEPS.indexOf(step);

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPass, setShowPass] = useState(false);

  const [secretPhrase] = useState<string[]>(generateSecretPhrase());
  const [phraseConfirmed, setPhraseConfirmed] = useState(false);
  const [phraseCopied, setPhraseCopied] = useState(false);

  const [mfaMethod, setMfaMethod] = useState<MFAMethod>('totp');
  const [totpCode] = useState(generateTOTPCode());
  const [userTOTP, setUserTOTP] = useState('');
  const [mfaError, setMfaError] = useState('');
  const [countdown, setCountdown] = useState(30);
  const [bioScanning, setBioScanning] = useState(false);
  const [bioProgress, setBioProgress] = useState(0);
  const [bioDone, setBioDone] = useState(false);

  const [blockchainAddress] = useState(generateBlockchainAddress());
  const [digitalId, setDigitalId] = useState('');
  const [idCopied, setIdCopied] = useState(false);

  const [cursor, setCursor] = useState(true);
  useEffect(() => {
    const t = setInterval(() => setCursor(c => !c), 530);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (step !== 'mfa-verify') return;
    setCountdown(30);
    const interval = setInterval(() => setCountdown(c => (c <= 1 ? 30 : c - 1)), 1000);
    return () => clearInterval(interval);
  }, [step]);

  useEffect(() => {
    setBioScanning(false); setBioProgress(0); setBioDone(false); setMfaError('');
  }, [mfaMethod]);

  function copyToClipboard(text: string, cb: () => void) {
    try {
      const ta = document.createElement('textarea');
      ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.focus(); ta.select();
      document.execCommand('copy'); document.body.removeChild(ta); cb();
    } catch { /* silent */ }
  }

  function startBioScan() {
    setBioScanning(true); setBioProgress(0);
    const interval = setInterval(() => {
      setBioProgress(prev => {
        if (prev >= 100) { clearInterval(interval); setBioScanning(false); setBioDone(true); return 100; }
        return prev + 4;
      });
    }, 80);
  }

  function handleMFAVerify() {
    if (mfaMethod === 'totp' && userTOTP.trim() !== totpCode) {
      setMfaError('INCORRECT CODE — USE THE CODE DISPLAYED ABOVE'); return;
    }
    const id = generateDigitalId(name || 'USER', blockchainAddress);
    setDigitalId(id); setMfaError(''); setStep('digital-id');
  }

  function handleFinish() {
    const user = { digitalId, address: blockchainAddress, name: name || 'OPERATOR' };
    setRegisteredUser(user);
    navigate('/dashboard');
  }

  const inputCls = "w-full bg-[#060b15] border border-[#2a4a7f] text-[#00ccaa] placeholder-[#2a4a7f] px-4 py-3 text-sm outline-none focus:border-[#00ccaa] transition tracking-widest font-mono";
  const labelCls = "text-[#8899bb] text-xs tracking-widest block mb-2";
  const primaryBtn = "w-full bg-[#1a4fd6] hover:bg-[#2962ff] disabled:opacity-30 disabled:cursor-not-allowed text-white tracking-[0.3em] text-xs py-3.5 flex items-center justify-center gap-2 transition uppercase font-bold";

  return (
    <div className="min-h-screen bg-[#080d1a] flex flex-col">

      {/* Header */}
      <header className="bg-[#0d1b3e] border-b-2 border-[#c0392b] px-6 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <Shield className="w-5 h-5 text-white" strokeWidth={2} />
          <span className="text-white tracking-widest text-sm font-bold uppercase">SENTINET — OPERATOR REGISTRATION</span>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <span className="text-[#8899bb]">DICT PUBLIC WI-FI PROTECTION SYSTEM</span>
          <span className="text-[#00ccaa]">NODE: POC-CTRL-HUB-01</span>
        </div>
      </header>

      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-lg">

          {/* Step indicator */}
          <div className="flex items-center mb-6">
            {STEP_LABELS.map((label, i) => (
              <React.Fragment key={label}>
                <div className="flex flex-col items-center gap-1 shrink-0">
                  <div className={`w-7 h-7 flex items-center justify-center text-xs font-bold border transition-all ${
                    i < stepIdx ? 'bg-[#00ccaa] border-[#00ccaa] text-[#080d1a]' :
                    i === stepIdx ? 'bg-[#1a4fd6] border-[#1a4fd6] text-white' :
                    'bg-transparent border-[#2a4a7f] text-[#2a4a7f]'
                  }`}>
                    {i < stepIdx ? <Check className="w-3.5 h-3.5" strokeWidth={3} /> : i + 1}
                  </div>
                  <span className={`text-[9px] tracking-widest hidden sm:block ${i === stepIdx ? 'text-[#00ccaa]' : 'text-[#2a4a7f]'}`}>{label}</span>
                </div>
                {i < STEP_LABELS.length - 1 && (
                  <div className={`flex-1 h-px mx-2 mb-4 transition-colors ${i < stepIdx ? 'bg-[#00ccaa]' : 'bg-[#1e3a5f]'}`} />
                )}
              </React.Fragment>
            ))}
          </div>

          {/* Panel */}
          <div className="border border-[#2a4a7f] bg-[#0d1b3e]">

            {/* Panel header */}
            <div className="bg-[#1a2f5e] border-b border-[#2a4a7f] px-6 py-4">
              <h2 className="text-white tracking-[0.2em] text-sm font-bold uppercase">
                {step === 'identity' && 'OPERATOR IDENTITY REGISTRATION'}
                {step === 'secret-phrase' && 'BLOCKCHAIN RECOVERY PHRASE'}
                {step === 'mfa-setup' && 'MULTI-FACTOR AUTHENTICATION SETUP'}
                {step === 'mfa-verify' && 'MFA VERIFICATION'}
                {step === 'digital-id' && 'DIGITAL ID ISSUED'}
              </h2>
              <p className="text-[#00ccaa] text-xs tracking-widest mt-1">
                STEP {stepIdx + 1} OF {STEPS.length} — CLEARANCE REGISTRATION PROTOCOL
              </p>
            </div>

            <div className="px-6 py-5">

              {/* STEP 1: Identity */}
              {step === 'identity' && (
                <div className="space-y-4">
                  <div>
                    <label className={labelCls}>FULL NAME</label>
                    <input className={inputCls} placeholder="e.g. JUAN DELA CRUZ" value={name} onChange={e => setName(e.target.value)} />
                  </div>
                  <div>
                    <label className={labelCls}>EMAIL ADDRESS</label>
                    <input className={inputCls} placeholder="operator@sentinet.gov" value={email} onChange={e => setEmail(e.target.value)} />
                  </div>
                  <div>
                    <label className={labelCls}>PASSWORD</label>
                    <div className="relative">
                      <input type={showPass ? 'text' : 'password'} className={inputCls + ' pr-10'} placeholder="SET ACCESS PASSWORD" value={password} onChange={e => setPassword(e.target.value)} />
                      <button onClick={() => setShowPass(!showPass)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#3a5070] hover:text-[#8899bb] transition">
                        {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                  <div>
                    <label className={labelCls}>CONFIRM PASSWORD</label>
                    <input type="password" className={inputCls} placeholder="CONFIRM PASSWORD" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} />
                  </div>
                  <button
                    onClick={() => setStep('secret-phrase')}
                    disabled={!name.trim() || !email.trim() || !password}
                    className={primaryBtn}
                  >
                    <ChevronRight className="w-4 h-4" strokeWidth={3} /> PROCEED TO NEXT STEP
                  </button>
                  <p className="text-[#3a5070] text-[10px] tracking-wider text-center">
                    ALREADY REGISTERED?{' '}
                    <button onClick={() => navigate('/login')} className="text-[#00ccaa] hover:text-white transition">AUTHENTICATE HERE</button>
                  </p>
                </div>
              )}

              {/* STEP 2: Secret Phrase */}
              {step === 'secret-phrase' && (
                <div className="space-y-4">
                  <div className="bg-[#060b15] border border-[#f59e0b]/30 p-4">
                    <p className="text-[#f59e0b] text-[10px] tracking-widest mb-3">⚠ CLASSIFIED — BLOCKCHAIN RECOVERY PHRASE. NEVER SHARE OR TRANSMIT.</p>
                    <div className="grid grid-cols-3 gap-2">
                      {secretPhrase.map((word, i) => (
                        <div key={i} className="flex items-center gap-2 border border-[#1e3a5f] px-2.5 py-2">
                          <span className="text-[#3a5070] text-[10px] w-4">{i + 1}.</span>
                          <span className="text-[#00ccaa] text-xs tracking-widest font-mono">{word}</span>
                        </div>
                      ))}
                    </div>
                    <button
                      onClick={() => copyToClipboard(secretPhrase.join(' '), () => { setPhraseCopied(true); setTimeout(() => setPhraseCopied(false), 2000); })}
                      className="w-full mt-3 border border-[#f59e0b]/30 text-[#f59e0b] text-[10px] tracking-widest py-2 hover:bg-[#f59e0b]/10 transition flex items-center justify-center gap-2"
                    >
                      {phraseCopied ? <><Check className="w-3 h-3" />COPIED</> : <><Copy className="w-3 h-3" />COPY TO SECURE STORAGE</>}
                    </button>
                  </div>
                  <label className="flex items-start gap-3 cursor-pointer">
                    <input type="checkbox" className="mt-0.5 accent-[#00ccaa]" checked={phraseConfirmed} onChange={e => setPhraseConfirmed(e.target.checked)} />
                    <span className="text-[#8899bb] text-[10px] leading-relaxed tracking-wider">I CONFIRM THIS PHRASE HAS BEEN STORED SECURELY. I UNDERSTAND IT CANNOT BE RECOVERED.</span>
                  </label>
                  <button onClick={() => setStep('mfa-setup')} className={primaryBtn}>
                    <ChevronRight className="w-4 h-4" strokeWidth={3} /> PHRASE SECURED — CONTINUE
                  </button>
                </div>
              )}

              {/* STEP 3: MFA Setup */}
              {step === 'mfa-setup' && (
                <div className="space-y-4">
                  <p className="text-[#8899bb] text-[10px] tracking-widest">SELECT AUTHENTICATION PROTOCOL:</p>
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      { id: 'totp' as MFAMethod, label: 'AUTHENTICATOR', icon: <Scan className="w-6 h-6" />, color: 'border-[#1a4fd6] bg-[#1a4fd6]/10 text-white' },
                      { id: 'face' as MFAMethod, label: 'FACE ID', icon: <ScanFace className="w-6 h-6" />, color: 'border-[#7c3aed] bg-[#7c3aed]/10 text-white' },
                      { id: 'fingerprint' as MFAMethod, label: 'FINGERPRINT', icon: <Fingerprint className="w-6 h-6" />, color: 'border-[#00ccaa] bg-[#00ccaa]/10 text-white' },
                    ].map(opt => (
                      <button
                        key={opt.id}
                        onClick={() => setMfaMethod(opt.id)}
                        className={`flex flex-col items-center gap-2 p-4 border-2 transition-all text-xs tracking-widest ${
                          mfaMethod === opt.id ? opt.color : 'border-[#1e3a5f] text-[#3a5070] hover:border-[#2a4a7f] hover:text-[#8899bb]'
                        }`}
                      >
                        {opt.icon}
                        {opt.label}
                      </button>
                    ))}
                  </div>

                  {mfaMethod === 'totp' && (
                    <div className="bg-[#060b15] border border-[#1a4fd6]/30 p-4 text-center">
                      <p className="text-[#8899bb] text-[10px] tracking-widest mb-3">SCAN QR CODE WITH AUTHENTICATOR APP</p>
                      <div className="inline-block bg-white p-2 mb-3">
                        <svg width="80" height="80" viewBox="0 0 120 120">
                          {Array.from({ length: 15 }).map((_, row) =>
                            Array.from({ length: 15 }).map((_, col) => {
                              const seed = (row * 17 + col * 13 + row * col) % 3;
                              const on = seed === 0 || (row < 4 && col < 4) || (row < 4 && col > 10) || (row > 10 && col < 4);
                              return on ? <rect key={`${row}-${col}`} x={col * 8} y={row * 8} width={7} height={7} fill="#0d1b3e" rx={1} /> : null;
                            })
                          )}
                        </svg>
                      </div>
                      <p className="text-[#00ccaa] text-[10px] tracking-widest font-mono">KEY: SNET-{blockchainAddress.substring(2, 10).toUpperCase()}</p>
                    </div>
                  )}
                  {mfaMethod === 'face' && (
                    <div className="bg-[#060b15] border border-[#7c3aed]/30 p-4 text-center">
                      <ScanFace className="w-10 h-10 text-[#7c3aed] mx-auto mb-2" strokeWidth={1.5} />
                      <p className="text-[#8899bb] text-[10px] tracking-widest">FACE CAPTURE WILL ACTIVATE IN VERIFICATION STEP</p>
                      <p className="text-[#3a5070] text-[10px] mt-1 tracking-wider">ENSURE ADEQUATE LIGHTING — FACE CAMERA DIRECTLY</p>
                    </div>
                  )}
                  {mfaMethod === 'fingerprint' && (
                    <div className="bg-[#060b15] border border-[#00ccaa]/30 p-4 text-center">
                      <Fingerprint className="w-10 h-10 text-[#00ccaa] mx-auto mb-2" strokeWidth={1.5} />
                      <p className="text-[#8899bb] text-[10px] tracking-widest">BIOMETRIC SENSOR ACTIVATES IN VERIFICATION STEP</p>
                      <p className="text-[#3a5070] text-[10px] mt-1 tracking-wider">PLACE REGISTERED FINGER ON SENSOR WHEN PROMPTED</p>
                    </div>
                  )}

                  <button onClick={() => setStep('mfa-verify')} className={primaryBtn}>
                    <ChevronRight className="w-4 h-4" strokeWidth={3} /> CONTINUE TO VERIFICATION
                  </button>
                </div>
              )}

              {/* STEP 4: MFA Verify */}
              {step === 'mfa-verify' && (
                <div className="space-y-4">
                  {mfaMethod === 'totp' && (
                    <>
                      <div className="bg-[#060b15] border border-[#1a4fd6]/30 p-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-[#8899bb] text-[10px] tracking-widest mb-1">DEMO AUTHENTICATOR CODE</p>
                            <p className="text-[#00ccaa] text-3xl tracking-[0.4em] font-bold font-mono">{totpCode}</p>
                          </div>
                          <div className="relative w-12 h-12">
                            <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
                              <circle cx="18" cy="18" r="15" stroke="#1e3a5f" strokeWidth="3" fill="none" />
                              <circle cx="18" cy="18" r="15" stroke="#1a4fd6" strokeWidth="3" fill="none"
                                strokeDasharray={`${2 * Math.PI * 15}`}
                                strokeDashoffset={`${2 * Math.PI * 15 * (1 - countdown / 30)}`}
                                strokeLinecap="round" />
                            </svg>
                            <span className="absolute inset-0 flex items-center justify-center text-white text-[10px]">{countdown}</span>
                          </div>
                        </div>
                      </div>
                      <div>
                        <label className={labelCls}>ENTER 6-DIGIT CODE</label>
                        <input
                          className={inputCls + ' text-center text-2xl tracking-[0.5em]'}
                          placeholder="000000" maxLength={6}
                          value={userTOTP}
                          onChange={e => setUserTOTP(e.target.value.replace(/\D/g, ''))}
                        />
                      </div>
                      {mfaError && (
                        <div className="flex items-center gap-2 border border-[#c0392b]/40 bg-[#c0392b]/10 text-[#ff6b6b] text-[10px] px-3 py-2 tracking-wider">
                          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />{mfaError}
                        </div>
                      )}
                      <button onClick={handleMFAVerify} className={primaryBtn}>
                        <Lock className="w-4 h-4" /> VERIFY &amp; ISSUE DIGITAL ID
                      </button>
                    </>
                  )}

                  {mfaMethod === 'face' && (
                    <>
                      <div className="flex justify-center">
                        <div className="relative w-52 h-52 border-2 border-[#7c3aed]/40 bg-[#060b15] flex items-center justify-center">
                          <div className="absolute top-2 left-2 w-5 h-5 border-t-2 border-l-2 border-[#7c3aed]" />
                          <div className="absolute top-2 right-2 w-5 h-5 border-t-2 border-r-2 border-[#7c3aed]" />
                          <div className="absolute bottom-2 left-2 w-5 h-5 border-b-2 border-l-2 border-[#7c3aed]" />
                          <div className="absolute bottom-2 right-2 w-5 h-5 border-b-2 border-r-2 border-[#7c3aed]" />
                          {bioDone ? (
                            <div className="flex flex-col items-center gap-2">
                              <div className="w-14 h-14 border-2 border-[#00ccaa] flex items-center justify-center">
                                <Check className="w-7 h-7 text-[#00ccaa]" strokeWidth={2.5} />
                              </div>
                              <span className="text-[#00ccaa] text-[10px] tracking-widest">FACE VERIFIED</span>
                            </div>
                          ) : bioScanning ? (
                            <div className="flex flex-col items-center gap-3 w-full px-8">
                              <ScanFace className="w-10 h-10 text-[#7c3aed] animate-pulse" strokeWidth={1.5} />
                              <div className="w-full bg-[#1e3a5f] h-1">
                                <div className="bg-[#7c3aed] h-1 transition-all duration-100" style={{ width: `${bioProgress}%` }} />
                              </div>
                              <span className="text-[#7c3aed] text-[10px] tracking-widest">SCANNING… {bioProgress}%</span>
                            </div>
                          ) : (
                            <ScanFace className="w-14 h-14 text-[#1e3a5f]" strokeWidth={1} />
                          )}
                        </div>
                      </div>
                      {!bioDone ? (
                        <button onClick={startBioScan} disabled={bioScanning} className="w-full border-2 border-[#7c3aed] text-[#7c3aed] hover:bg-[#7c3aed]/10 disabled:opacity-40 text-xs tracking-widest py-3 flex items-center justify-center gap-2 transition uppercase">
                          <ScanFace className="w-4 h-4" /> {bioScanning ? 'SCANNING…' : 'INITIATE FACE SCAN'}
                        </button>
                      ) : (
                        <button onClick={handleMFAVerify} className={primaryBtn}>
                          <Lock className="w-4 h-4" /> VERIFY &amp; ISSUE DIGITAL ID
                        </button>
                      )}
                    </>
                  )}

                  {mfaMethod === 'fingerprint' && (
                    <>
                      <div className="flex justify-center">
                        <div className="relative w-44 h-44 border-2 border-[#00ccaa]/30 bg-[#060b15] flex items-center justify-center">
                          {bioScanning && !bioDone && (
                            <div className="absolute inset-0 border border-[#00ccaa]/20 animate-ping" />
                          )}
                          {bioDone ? (
                            <div className="flex flex-col items-center gap-2">
                              <div className="w-14 h-14 border-2 border-[#00ccaa] flex items-center justify-center">
                                <Check className="w-7 h-7 text-[#00ccaa]" strokeWidth={2.5} />
                              </div>
                              <span className="text-[#00ccaa] text-[10px] tracking-widest">VERIFIED</span>
                            </div>
                          ) : (
                            <Fingerprint className={`w-20 h-20 transition-colors ${bioScanning ? 'text-[#00ccaa]' : 'text-[#1e3a5f]'}`} strokeWidth={0.8} />
                          )}
                        </div>
                      </div>
                      {!bioDone && (
                        <div className="bg-[#1e3a5f] h-1 w-full">
                          <div className="bg-[#00ccaa] h-1 transition-all duration-100" style={{ width: `${bioProgress}%` }} />
                        </div>
                      )}
                      {!bioDone ? (
                        <button onClick={startBioScan} disabled={bioScanning} className="w-full border-2 border-[#00ccaa] text-[#00ccaa] hover:bg-[#00ccaa]/10 disabled:opacity-40 text-xs tracking-widest py-3 flex items-center justify-center gap-2 transition uppercase">
                          <Fingerprint className="w-4 h-4" /> {bioScanning ? `READING… ${bioProgress}%` : 'PLACE FINGER ON SENSOR'}
                        </button>
                      ) : (
                        <button onClick={handleMFAVerify} className={primaryBtn}>
                          <Lock className="w-4 h-4" /> VERIFY &amp; ISSUE DIGITAL ID
                        </button>
                      )}
                    </>
                  )}

                  <button onClick={() => setStep('mfa-setup')} className="w-full text-[#3a5070] hover:text-[#8899bb] text-[10px] tracking-widest py-1.5 transition">
                    ← CHANGE MFA METHOD
                  </button>
                </div>
              )}

              {/* STEP 5: Digital ID */}
              {step === 'digital-id' && (
                <div className="space-y-4">
                  <div className="bg-[#060b15] border border-[#00ccaa]/30 p-5">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-2">
                        <Shield className="w-4 h-4 text-[#00ccaa]" strokeWidth={2} />
                        <span className="text-[#00ccaa] text-[10px] tracking-[0.3em]">DIGITAL ID — DICT / SENTINET</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <div className="w-1.5 h-1.5 bg-[#00ccaa] animate-pulse" />
                        <span className="text-[#00ccaa] text-[9px] tracking-widest">VERIFIED</span>
                      </div>
                    </div>
                    <div className="space-y-3">
                      <div>
                        <p className="text-[#3a5070] text-[9px] tracking-widest mb-0.5">OPERATOR NAME</p>
                        <p className="text-white text-sm tracking-widest">{name || 'OPERATOR'}</p>
                      </div>
                      <div>
                        <p className="text-[#3a5070] text-[9px] tracking-widest mb-0.5">BLOCKCHAIN ADDRESS</p>
                        <p className="text-[#1a4fd6] text-[10px] break-all font-mono">{blockchainAddress}</p>
                      </div>
                      <div>
                        <p className="text-[#3a5070] text-[9px] tracking-widest mb-0.5">DIGITAL ID</p>
                        <div className="flex items-center gap-2">
                          <p className="text-[#00ccaa] text-sm tracking-widest flex-1 font-mono">{digitalId}</p>
                          <button onClick={() => copyToClipboard(digitalId, () => { setIdCopied(true); setTimeout(() => setIdCopied(false), 2000); })}
                            className="border border-[#2a4a7f] p-1.5 text-[#3a5070] hover:text-[#00ccaa] hover:border-[#00ccaa] transition">
                            {idCopied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                          </button>
                        </div>
                      </div>
                    </div>
                    <div className="mt-4 pt-3 border-t border-[#1e3a5f] flex items-center justify-between">
                      <span className="text-[#3a5070] text-[9px] font-mono">ISSUED: {new Date().toLocaleDateString()}</span>
                      <span className="text-[#3a5070] text-[9px] font-mono">POC-v2.6.9</span>
                    </div>
                  </div>

                  <div className="border border-[#f59e0b]/20 bg-[#f59e0b]/5 px-4 py-3">
                    <p className="text-[#f59e0b] text-[10px] tracking-widest">⚠ SAVE YOUR DIGITAL ID AND SECRET PHRASE. REQUIRED FOR ACCOUNT RECOVERY.</p>
                  </div>

                  <button onClick={handleFinish} className={primaryBtn.replace('disabled:opacity-30 disabled:cursor-not-allowed', '') + ' bg-[#00aa55] hover:bg-[#00cc66]'}>
                    <Shield className="w-4 h-4" /> LAUNCH SENTINET AGENT
                  </button>
                </div>
              )}

            </div>

            {/* Panel footer */}
            <div className="border-t border-[#2a4a7f] px-6 py-3 flex items-center justify-between">
              <span className="text-[#3a5070] text-[10px] tracking-widest">CLASSIFIED // AUTHORIZED USE ONLY</span>
              <span className="text-[#3a5070] text-[10px] tracking-widest">POC-v2.6.9</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
