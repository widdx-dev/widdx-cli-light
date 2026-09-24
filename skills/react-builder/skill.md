---
name: react-builder
description: Build production React/Next.js apps with Vite, TypeScript, Tailwind, Zustand, and Framer Motion
icon: ⚛️
---

# React Builder Skill

You build **complete, working React projects**. You NEVER explain — you EXECUTE.

## Scaffold React (Vite + TS)
```bash
npm create vite@latest . -- --template react-ts
npm install
npm install react-router-dom zustand tailwindcss @tailwindcss/vite framer-motion
```

## Required files to write

### `vite.config.ts`
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
export default defineConfig({
  plugins: [react(), tailwindcss()],
})
```

### `src/index.css`
```css
@import "tailwindcss";
```

### `src/main.tsx`
```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
```

### `src/App.tsx`
Full App with Routes, Layout, all pages, loading states, error boundaries.

### `src/pages/` — All page components
- HomePage, AboutPage, ContactPage, NotFoundPage (or as requested)

### `src/components/` — Reusable UI
- Layout (header, footer, sidebar)
- Loading spinner, ErrorFallback

## Build & verify
```bash
npm run build
```
If it fails: **read the errors and fix every file** until `npm run build` succeeds.

## Next.js variant (if requested)
```bash
npx create-next-app@latest . --typescript --tailwind --eslint --app
npm install zustand framer-motion
```
Write `app/page.tsx`, `app/layout.tsx`, `app/globals.css`. Build with `npm run build`.

## Rules
- ALWAYS run `npm run build` at the end
- NEVER say "done" until the build succeeds
- Use `bash` to run commands, not explanations
