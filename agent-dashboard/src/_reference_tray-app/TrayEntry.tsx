import React from 'react';
import { createMemoryRouter, RouterProvider, Outlet } from 'react-router';
import { Toaster } from 'sonner';
import AgentToggle from './AgentToggle';

/**
 * SYSTEM TRAY CONTROLLER — REFERENCE CODE ONLY.
 *
 * This file is NOT imported anywhere in the Figma Make web app. It is preserved
 * here as a standalone UI reference to be ported into a native tray process
 * (Python `pystray` + a webview, or Electron / Tauri). See README.md.
 *
 * In the native app, `onOpenDashboard` should be replaced with a real action
 * that opens the locally-served Agent Dashboard (e.g. open the browser at the
 * daemon's loopback URL). Here it is a harmless no-op so the file is fully
 * self-contained and runnable in isolation.
 */
export function TrayApp({ onOpenDashboard }: { onOpenDashboard?: () => void } = {}) {
  const handleOpenDashboard = onOpenDashboard ?? (() => {
    // In the native build: launch the Agent Dashboard (loopback URL).
    console.info('[tray] Open Agent Dashboard requested');
  });

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
        { index: true, element: <AgentToggle onOpenDashboard={handleOpenDashboard} /> },
        { path: '*', element: <AgentToggle onOpenDashboard={handleOpenDashboard} /> },
      ],
    },
  ]);

  return <RouterProvider router={router} />;
}
