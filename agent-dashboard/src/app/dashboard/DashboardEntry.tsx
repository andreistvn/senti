import React from 'react';
import { createMemoryRouter, RouterProvider, Outlet } from 'react-router';
import { Toaster } from 'sonner';
import Register from '../components/Register';
import Login from '../components/Login';
import Dashboard from '../components/Dashboard';

const router = createMemoryRouter([
  {
    path: '/',
    element: (
      <div className="min-h-screen flex flex-col font-sans">
        <div className="flex-1">
          <Outlet />
        </div>
        <Toaster
          position="bottom-right"
          theme="dark"
          toastOptions={{
            style: {
              background: '#0d1b3e',
              border: '1px solid #c0392b',
              color: '#fff',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '11px',
              letterSpacing: '0.05em',
            },
          }}
        />
      </div>
    ),
    children: [
      { index: true, Component: Register },
      { path: 'login', Component: Login },
      { path: 'dashboard', Component: Dashboard },
      { path: '*', Component: Register },
    ],
  },
]);

export function DashboardApp() {
  return <RouterProvider router={router} />;
}
