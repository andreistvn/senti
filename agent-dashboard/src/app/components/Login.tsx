import React, { useState } from 'react';
import { useNavigate } from 'react-router';
import { Shield, Eye, EyeOff, ChevronRight } from 'lucide-react';

// Boot log and SEC status panels removed per request

export default function Login() {
  const navigate = useNavigate();
  const [digitalId, setDigitalId] = useState('');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [systemActive, setSystemActive] = useState(true);

  // systemActive controls the header system indicator

  function handleLogin() {
    if (!digitalId.trim() || !password) return;
    navigate('/dashboard');
  }

  return (
    <div className="min-h-screen bg-[#f3f6f9] flex flex-col">

      {/* Header */}
      <header className="bg-[#08273f] border-b border-[#e6eef7] px-6 py-3 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
          <Shield className="w-5 h-5 text-white" strokeWidth={2} />
          <span className="text-white tracking-widest text-sm font-bold uppercase">SENTINET — LOG IN</span>
        </div>
        <div className="flex items-center gap-6 text-xs">
          <button
            onClick={() => setSystemActive(s => !s)}
            className={`flex items-center gap-2 px-3 py-1 rounded tracking-widest text-xs font-semibold transition bg-white`}
          >
            <span className={`w-2 h-2 rounded-full inline-block ${systemActive ? 'bg-[#00c781]' : 'bg-[#ff6b6b]'}`}></span>
            {systemActive ? 'SYSTEM ACTIVE' : 'ACTIVATE SYSTEM'}
          </button>
        </div>
      </header>

      {/* Three-panel body */}
      <div className="flex flex-1 overflow-hidden">

        {/* CENTER — Auth Modal (now full width) */}

        {/* CENTER — Auth Modal */}
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="w-full max-w-md border border-gray-200 bg-white shadow-sm">

            {/* Modal header */}
            <div className="bg-white border-b border-gray-100 px-6 py-4">
              <h1 className="text-[#0b2540] tracking-[0.02em] text-lg font-bold">Administrator Authentication</h1>
            </div>

            {/* Modal body */}
            <div className="px-6 py-6 space-y-5">
              <div>
                <label className="text-[#8899bb] text-xs tracking-widest block mb-2">DIGITAL ID</label>
                <input
                  className="w-full bg-white border border-gray-200 text-[#0b2540] placeholder-[#9aa4b2] px-4 py-3 text-sm outline-none focus:border-[#1a73e8] transition tracking-widest"
                  placeholder="ADM-XXXX-XXXXX"
                  value={digitalId}
                  onChange={e => setDigitalId(e.target.value)}
                />
                <p className="text-[#3a5070] text-[10px] mt-1 tracking-wider"></p>
              </div>

              <div>
                <label className="text-[#8899bb] text-xs tracking-widest block mb-2">PASSWORD</label>
                <div className="relative">
                  <input
                    type={showPass ? 'text' : 'password'}
                    className="w-full bg-white border border-gray-200 text-[#0b2540] placeholder-[#9aa4b2] px-4 py-3 text-sm pr-10 outline-none focus:border-[#1a73e8] transition tracking-widest"
                    placeholder="••••••••••••••"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleLogin()}
                  />
                  <button onClick={() => setShowPass(!showPass)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#667085] hover:text-[#0b2540] transition">
                    {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-[#3a5070] text-[10px] mt-1 tracking-wider"></p>
              </div>
              <button
                onClick={handleLogin}
                disabled={!digitalId.trim() || !password}
                className="w-full bg-[#1a73e8] hover:bg-[#1667d0] disabled:opacity-40 disabled:cursor-not-allowed text-white tracking-[0.02em] text-sm py-3 flex items-center justify-center gap-3 transition font-semibold rounded"
              >
                <ChevronRight className="w-4 h-4" strokeWidth={3} />
                Authenticate
              </button>
            </div>

            {/* Modal footer */}
            <div className="border-t border-gray-100 px-6 py-3 flex items-center justify-between">
              <span className="text-[#7b8794] text-[12px]">CLASSIFIED // AUTHORIZED USE ONLY</span>
              <span className="text-[#7b8794] text-[12px]">POC-v2.6.9</span>
            </div>
          </div>
          <p className="absolute bottom-8 text-[#475569] text-xs tracking-wider">
            NO ACCOUNT? <button onClick={() => navigate('/')} className="text-[#1a73e8] hover:text-[#0b2540] transition">REGISTER HERE</button>
          </p>
        </div>

        {/* RIGHT panel removed per request */}

      </div>
    </div>
  );
}
