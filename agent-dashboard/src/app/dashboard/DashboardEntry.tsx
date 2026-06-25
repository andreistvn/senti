import React, { useContext } from 'react';
import { createMemoryRouter, RouterProvider, Outlet, useNavigate } from 'react-router';
import { Toaster } from 'sonner';
import { AuthContext } from '../App';
import Register from '../components/Register';
import Login from '../components/Login';
import Dashboard from '../components/Dashboard';

function DashboardRouteWrapper() {
  const navigate = useNavigate();
  const { setRegisteredUser } = useContext(AuthContext);

  const handleLogout = () => {
    setRegisteredUser(null);
    navigate('/login', { replace: true });
  };

  return <Dashboard onLogout={handleLogout} />;
}

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
      { index: true, Component: Register },
      { path: 'login', Component: Login },
      { path: 'dashboard', Component: DashboardRouteWrapper },
      { path: '*', Component: Register },
    ],
  },
]);

export function DashboardApp() {
  return <RouterProvider router={router} />;
}
