import React from 'react';
import { createBrowserRouter, redirect } from 'react-router';
import LoginRoute from './components/LoginRoute';
import DashboardRoute from './components/DashboardRoute';

// Simple in-memory auth state shared across routes
export const authState = { authenticated: false };

export const router = createBrowserRouter([
  {
    path: '/',
    element: <LoginRoute />,
  },
  {
    path: '/dashboard',
    loader: () => {
      if (!authState.authenticated) return redirect('/');
      return null;
    },
    element: <DashboardRoute />,
  },
]);
