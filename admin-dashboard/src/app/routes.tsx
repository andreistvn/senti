import React from 'react';
import { createBrowserRouter, redirect } from 'react-router';
import LoginRoute from './components/LoginRoute';
import DashboardRoute from './components/DashboardRoute';
import { isAdminAuthenticated } from './lib/adminApi';

async function requireAdminAuth() {
  if (!(await isAdminAuthenticated())) return redirect('/');
  return null;
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <LoginRoute />,
  },
  {
    path: '/dashboard',
    loader: requireAdminAuth,
    element: <DashboardRoute />,
  },
]);
