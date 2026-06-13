import React from 'react';
import { useNavigate } from 'react-router';
import { authState } from '../routes';
import Dashboard from './Dashboard';


export default function DashboardRoute() {
  const navigate = useNavigate();

  const handleLogout = () => {
    authState.authenticated = false;
    navigate('/', { replace: true });
  };

  return <Dashboard onLogout={handleLogout} />;
}
