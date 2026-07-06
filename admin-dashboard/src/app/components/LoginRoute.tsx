import React, { useEffect } from 'react';
import { useNavigate } from 'react-router';
import LoginPage from './LoginPage';
import { getAdminSession } from '../lib/adminApi';

export default function LoginRoute() {
  const navigate = useNavigate();

  useEffect(() => {
    void (async () => {
      if ((await getAdminSession()).authenticated) navigate('/dashboard', { replace: true });
    })();
  }, []);

  const handleLogin = () => {
    navigate('/dashboard', { replace: true });
  };

  return <LoginPage onLogin={handleLogin} />;
}
