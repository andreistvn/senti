import React, { useState } from 'react';
import type { RegisteredUser } from './components/Register';
import { DashboardApp } from './dashboard/DashboardEntry';

export const AuthContext = React.createContext<{
  registeredUser: RegisteredUser | null;
  setRegisteredUser: (u: RegisteredUser) => void;
}>({ registeredUser: null, setRegisteredUser: () => {} });

export default function App() {
  const [registeredUser, setRegisteredUser] = useState<RegisteredUser | null>(null);

  return (
    <AuthContext.Provider value={{ registeredUser, setRegisteredUser }}>
      <div className="min-h-screen bg-[#060a14]">
        <DashboardApp />
      </div>
    </AuthContext.Provider>
  );
}
