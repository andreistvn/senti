import React, { useEffect } from 'react';
import { useNavigate } from 'react-router';
import LoginPage from './LoginPage';
import { authState } from '../routes';

export default function LoginRoute() {
  const navigate = useNavigate();

  useEffect(() => {
    if (authState.authenticated) navigate('/dashboard', { replace: true });
  }, []);

  const handleLogin = () => {
    authState.authenticated = true;
    navigate('/dashboard', { replace: true });
  };

  return <LoginPage onLogin={handleLogin} />;
}
