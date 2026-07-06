import React, { useState } from 'react';
import type { RegisteredUser } from './components/Register';
import { DashboardApp } from './dashboard/DashboardEntry';

export interface AuthContextValue {
  registeredUser: RegisteredUser | null;
  setRegisteredUser: React.Dispatch<React.SetStateAction<RegisteredUser | null>>;
}

export const AuthContext = React.createContext<AuthContextValue>({
  registeredUser: null,
  setRegisteredUser: () => {},
});

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
