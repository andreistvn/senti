import React from 'react';
import { createMemoryRouter, RouterProvider, Outlet } from 'react-router';
import { Toaster } from 'sonner';
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
              background: '#9daedb',
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
      { index: true, Component: Dashboard },
      { path: '*', Component: Dashboard },
    ],
  },
]);

export function DashboardApp() {
  return <RouterProvider router={router} />;
}
