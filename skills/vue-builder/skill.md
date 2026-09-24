---
name: vue-builder
description: Build production Vue 3 / Nuxt apps with Pinia, Vue Router, and Tailwind
icon: 💚
---

# Vue Builder Skill

You build **complete, working Vue 3 projects**. You NEVER explain — you EXECUTE.

## Scaffold Vue (Vite + TS)
```bash
npm create vite@latest . -- --template vue-ts
npm install
npm install vue-router pinia tailwindcss @tailwindcss/vite
```

## Required files

### `vite.config.ts`
```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
export default defineConfig({
  plugins: [vue(), tailwindcss()],
})
```

### `src/main.ts`
```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'

createApp(App).use(createPinia()).use(router).mount('#app')
```

### `src/App.vue`
Root component with `<router-view />`, layout, transitions.

### `src/router/index.ts`
Full route definitions with lazy loading (`defineAsyncComponent`).

### `src/pages/` — All page components
Options API or Composition API with `<script setup lang="ts">`.

### `src/stores/` — Pinia stores
With actions, getters, proper typing.

### `src/components/` — Reusable UI
Layout, navigation, cards, modals.

### `src/style.css`
```css
@import "tailwindcss";
```

## Build & verify
```bash
npm run build
```
Fix ALL errors until build passes.

## Nuxt variant (if requested)
```bash
npx nuxi@latest init . --t yes
npm install pinia @pinia/nuxt
```
Use `pages/`, `layouts/`, `components/`, `composables/` directories.
Build with `npm run build`.

## Rules
- Use `<script setup lang="ts">` for all components
- Lazy-load all routes with `defineAsyncComponent`
- ALWAYS run `npm run build` before declaring done
- Use `bash` to run commands, not explanations
