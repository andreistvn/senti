# Plan: Make SentiNet Admin Dashboard run standalone (local Vite)

## Context
This project is a Figma Make app. Figma Make hides the local Vite entry scaffolding
(`index.html`, `src/main.tsx`, root `tsconfig.json`) and uses `__figma__entrypoint__.ts`
plus `figma:*` virtual modules instead. To export and run it on a Mac inside
`root/admin-dashboard/` beside `dashboard/` (port 5173) and `tray-app/`
(127.0.0.1:8770), we must add the standard Vite entry files, pick a non-colliding
port (5175), and make `npm install` pull `react`/`react-dom`.

Verified facts from the codebase:
- Style entry: `src/styles/index.css` (matches `__figma__entrypoint__.ts`).
- App entry: `src/app/App.tsx`, default export, renders `<RouterProvider>` using
  `createBrowserRouter` (`src/app/routes.tsx`). Browser router works fine under plain Vite.
- React versions targeted: `react` / `react-dom` `18.3.1` (currently in `peerDependencies`).
- No `figma:asset` / `figma:foundry` imports and no `../../` parent imports exist in
  `src` — only `__figma__entrypoint__.ts` references `figma:foundry-client-api`. So the
  app is already self-contained; we just don't use the figma entrypoint locally.

## Changes

### 1. `vite.config.ts`
Add to the `defineConfig({...})` object (e.g. after `plugins`):
```ts
server: { port: 5175, strictPort: true },
preview: { port: 5175 },
```
Leave `react()`, `tailwindcss()`, the `@` alias, and `assetsInclude` untouched.

### 2. `package.json`
- Change `"name"` to `"sentinet-admin-dashboard"`.
- Add scripts: `"dev": "vite"`, `"preview": "vite preview"` (keep `"build"`).
- Add `"react": "18.3.1"` and `"react-dom": "18.3.1"` to `"dependencies"`.
- Leave existing `peerDependencies` / `peerDependenciesMeta` as-is (harmless); the new
  `dependencies` entries are what `npm install` uses.

### 3. New `src/main.tsx`
```tsx
import { createRoot } from 'react-dom/client';
import './styles/index.css';
import App from './app/App';

createRoot(document.getElementById('root')!).render(<App />);
```

### 4. New root `tsconfig.json` (single flat file, no `references`)
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src"]
}
```
(`paths` mirrors the `@` alias in `vite.config.ts`.)

### 5. New `README.md` at project root
Short description: what the admin dashboard does (SentiNet Relay Node monitoring —
threat analytics, policy configurator, node topology/health, blockchain metrics),
that it runs on **port 5175** via `npm install && npm run dev`, and that it's designed
to sit beside `/dashboard` (5173) and `/tray-app` (8770) under a shared root.

### Self-containment
No code changes needed — confirmed no imports reference parent folders or sibling
projects, and no `figma:asset` modules are used in `src`. The `figma:*` references
live only in `__figma__entrypoint__.ts`, which the local build ignores (we use
`src/main.tsx` via `index.html` instead).

## Deliverables to report back to the user
**(a) Exact `index.html` to paste at project root** (Figma Make blocks `.html` creation):
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>SentiNet Admin Dashboard</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

**(b) Run steps:**
```
cd admin-dashboard
npm install
npm run dev
```
Opens on http://localhost:5175 (strict port — will fail loudly rather than collide
with 5173/8770).

## Verification
- `npm install` resolves react/react-dom (now in dependencies).
- `npm run dev` starts Vite on 5175; visiting `/` shows login, `/dashboard` redirects
  to `/` when unauthenticated (existing loader behavior).
- Confirm no console errors about missing `figma:*` modules (the local entry path
  bypasses `__figma__entrypoint__.ts`).
