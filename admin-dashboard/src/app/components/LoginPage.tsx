import React, { useState } from 'react';
import { signInAdmin } from '../lib/adminApi';

type AuthStep = 'credentials' | 'verifying' | 'success';

interface LoginPageProps {
  onLogin: () => void;
}

export default function LoginPage({ onLogin }: LoginPageProps) {
  const [digitalId, setDigitalId] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [step, setStep] = useState<AuthStep>('credentials');
  const [credError, setCredError] = useState('');

  // The relay checks the password; this page only sends it and reports back.
  const handleCredSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (digitalId.trim() === '' || password === '') {
      setCredError('ALL FIELDS REQUIRED.');
      return;
    }
    setCredError('');
    setStep('verifying');
    const result = await signInAdmin(digitalId.trim(), password);
    if (!result.ok) {
      setPassword('');
      setCredError(result.message.toUpperCase());
      setStep('credentials');
      return;
    }
    setStep('success');
    setTimeout(onLogin, 800);
  };

  return (
    <div className="min-h-screen w-full bg-[#f3f6f9] flex flex-col font-['Inter',_sans-serif] antialiased">

      {/* Top bar */}
      <header className="bg-[#0d1b3e] border-b-2 border-[#c0392b] px-6 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-white tracking-widest text-sm font-bold uppercase">Admin Sentinet</span>
        </div>
      </header>

      <div className="flex flex-1">

        {/* Center — login form */}
        <div className="flex-1 flex items-center justify-center p-8 bg-[#f3f6f9]">
          <div className="w-full max-w-[460px]">

            {/* Title block */}
            <div className="border border-gray-200 bg-white p-5 mb-0 shadow-sm rounded-t">
              <div className="text-[#0b2540] font-bold tracking-[0.02em] text-base">Administrator Authentication</div>
            </div>

            <div className="border border-t-0 border-gray-100 bg-white p-8 shadow-sm rounded-b">

              {/* Credentials */}
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
                      className="w-full bg-white border border-gray-200 text-[#0b2540] text-sm px-4 py-3 placeholder-[#9aa4b2] focus:outline-none focus:border-[#1a73e8] tracking-widest"
                      autoComplete="username"
                      spellCheck={false}
                      autoFocus
                    />
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
                        autoComplete="current-password"
                        className="w-full bg-white border border-gray-200 text-[#0b2540] text-sm px-4 py-3 pr-16 placeholder-[#9aa4b2] focus:outline-none focus:border-[#1a73e8]"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(v => !v)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-[#475569] hover:text-[#94A3B8] text-[10px] font-bold uppercase tracking-widest"
                      >
                        {showPassword ? 'Hide' : 'Show'}
                      </button>
                    </div>
                  </div>

                  {credError && (
                    <div className="flex items-center gap-2 bg-[#7F1D1D] border-2 border-[#DC2626] px-4 py-3 text-[#FCA5A5] text-xs font-bold uppercase tracking-widest font-['JetBrains_Mono',_monospace]">
                      {credError}
                    </div>
                  )}

                  <button
                    type="submit"
                    className="w-full bg-[#1a73e8] hover:bg-[#1667d0] border border-[#1a73e8] text-white font-semibold tracking-[0.02em] py-3 flex items-center justify-center gap-3 text-sm transition rounded"
                  >
                    Authenticate
                  </button>
                </form>
              )}

              {/* Verifying with the relay */}
              {step === 'verifying' && (
                <div className="space-y-4 py-6 flex flex-col items-center text-center">
                  <div className="text-[#0b2540] font-['JetBrains_Mono',_monospace] text-sm uppercase tracking-widest">
                    Verifying credentials...
                  </div>
                </div>
              )}

              {/* Signed in */}
              {step === 'success' && (
                <div className="space-y-4 py-6 flex flex-col items-center text-center">
                  <div className="text-[#0b2540] font-bold uppercase tracking-widest text-base">ACCESS GRANTED</div>
                  <div className="text-[#16A34A] font-['JetBrains_Mono',_monospace] text-xs uppercase tracking-widest">Loading dashboard...</div>
                </div>
              )}

            </div>

            {/* Footer strip */}
            <div className="border border-t-0 border-gray-100 bg-white px-5 py-3 flex justify-between items-center">
              <span className="text-[#475569] text-[10px] font-['JetBrains_Mono',_monospace] uppercase tracking-widest">CLASSIFIED // AUTHORIZED USE ONLY</span>
              <span className="text-[#475569] text-[10px] font-['JetBrains_Mono',_monospace]">POC-v2.4.9</span>
            </div>
          </div>
        </div>

      </div>

    </div>
  );
}