---
name: express-builder
description: Build production Node.js/Express & NestJS APIs with TypeScript, Prisma, and full test suite
icon: 🚀
---

# Express Builder Skill

You build **complete, working Node.js APIs**. You NEVER explain — you EXECUTE.

## Scaffold Express + TypeScript
```bash
npm init -y
npm install express cors helmet dotenv
npm install -D typescript @types/node @types/express @types/cors tsx
npx tsc --init --target es2022 --module node16 --outDir dist --rootDir src --strict true
```

## Required files

### `src/index.ts`
```typescript
import express from 'express'
import cors from 'cors'
import helmet from 'helmet'
import 'dotenv/config'

const app = express()
app.use(cors()).use(helmet()).use(express.json())

// Routes
app.get('/api/status', (_, res) => res.json({ ok: true }))

app.listen(process.env.PORT || 3000, () => {
  console.log(`Server on port ${process.env.PORT || 3000}`)
})
```

### `src/routes/` — Route modules
With express.Router(), validation, error handling.

### `src/middleware/` — Custom middleware
Auth, error handler, validation, rate limiting.

### `src/models/` — Data models
TypeScript interfaces/types for all data structures.

### `src/services/` — Business logic
Separated from route handlers.

### `tsconfig.json`
Strict mode, proper path aliases.

### `.env.example`
```
PORT=3000
DATABASE_URL=
JWT_SECRET=
```

## Add database (if needed)
```bash
npm install prisma @prisma/client
npx prisma init
```
Write `prisma/schema.prisma`, run `npx prisma generate && npx prisma db push`

## Verify
```bash
npx tsc --noEmit
```

## NestJS variant (if requested)
```bash
npx @nestjs/cli@latest new . --skip-git --package-manager npm
```
Write modules, controllers, services, DTOs, guards.
Build with: `npm run build`

## Rules
- Add proper error handling middleware
- Use environment variables for config
- Include CORS configuration
- ALWAYS run `npx tsc --noEmit` to verify types
- Use `bash` to run commands, not explanations
