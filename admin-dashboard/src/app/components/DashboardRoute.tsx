import React from 'react';
import { useNavigate } from 'react-router';
import { signOutAdmin } from '../lib/adminApi';
import Dashboard from './Dashboard';


export default function DashboardRoute() {
  const navigate = useNavigate();

  const handleLogout = async () => {
    await signOutAdmin();
    navigate('/', { replace: true });
  };

  return <Dashboard onLogout={handleLogout} />;
}
