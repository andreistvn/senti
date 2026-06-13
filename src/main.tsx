import React from 'react';
import { createRoot } from 'react-dom/client';
import './styles/index.css';
import App from './app/App';

// Local Vite entry point (used by `npm run dev`). This mirrors
// __figma__entrypoint__.ts but omits the Figma-only `figma:` virtual module,
// so it runs in a plain browser.
const container = document.getElementById('root');
if (!container) throw new Error('Root element #root not found in index.html');

createRoot(container).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
