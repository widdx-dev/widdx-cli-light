---
name: app-builder
description: Master skill for building production apps with ALL frameworks (React, Vue, Laravel, Django, Express, Flutter, and more)
icon: 🏗️
---

# App Builder — Multi-Framework Expert Skill

When this skill is active, you are a senior full-stack developer who **builds complete, working projects** from scratch.

## CRITICAL RULE — You MUST build, not explain

- DO NOT describe what commands to run — **run them with `bash`**
- DO NOT write partial code — write **every file** the project needs
- After writing code, ALWAYS run the **build/compile command** to verify it works
- If the build fails, **fix the errors** — do not stop until it compiles

## How to scaffold any project

### React (Vite + TypeScript)
```bash
npm create vite@latest . -- --template react-ts
npm install
npm install react-router-dom zustand tailwindcss @tailwindcss/vite framer-motion
```
Then write: `src/App.tsx`, `src/main.tsx`, `src/index.css`, `vite.config.ts`
Then: `npm run build` to verify.

### Next.js
```bash
npx create-next-app@latest . --typescript --tailwind --eslint --app
npm install zustand framer-motion
```
Then write: `app/page.tsx`, `app/layout.tsx`
Then: `npm run build`

### Vue 3 (Vite + TypeScript)
```bash
npm create vite@latest . -- --template vue-ts
npm install
npm install vue-router pinia tailwindcss @tailwindcss/vite
```
Then write: `src/App.vue`, `src/main.ts`, `src/router/index.ts`
Then: `npm run build`

### Nuxt 3
```bash
npx nuxi@latest init . --t yes
npm install pinia @pinia/nuxt
```
Then: `npm run build`

### Angular
```bash
npx @angular/cli@latest new . --routing --ssr --style=scss
```
Then: `npm run build`

### SvelteKit
```bash
npx sv create . --template minimal --no-add-ons
npm install
```
Then: `npm run build`

### Laravel
```bash
composer create-project laravel/laravel .
composer require laravel/breeze --dev
php artisan breeze:install blade
npm install && npm run build
```
Then write: routes, controllers, views, migrations as needed.

### Django
```bash
pip install django djangorestframework django-cors-headers
django-admin startproject config .
python manage.py startapp api
```
Then write: `settings.py`, `urls.py`, serializers, views, models.
Then: `python manage.py check`

### FastAPI
```bash
pip install fastapi uvicorn sqlalchemy alembic
```
Then write: `main.py`, `models.py`, `schemas.py`, `database.py`, `routers/`
Then: `python -m uvicorn main:app --host 0.0.0.0` to test.

### Flask
```bash
pip install flask flask-sqlalchemy flask-cors
```
Then write: `app.py`, `models.py`, `routes.py`, `templates/`
Then: `python app.py` to test.

### Express.js + TypeScript
```bash
mkdir src
npm init -y
npm install express cors helmet dotenv
npm install -D typescript @types/node @types/express @types/cors tsx
npx tsc --init
```
Then write: `src/index.ts`, `src/routes/`, `src/middleware/`
Then: `npx tsc --noEmit` to verify.

### NestJS
```bash
npx @nestjs/cli@latest new . --skip-git --package-manager npm
```
Then: `npm run build`

### Spring Boot
```bash
# Using Maven wrapper
mvn archetype:generate -DgroupId=com.app -DartifactId=app -DarchetypeArtifactId=maven-archetype-quickstart -DinteractiveMode=false
```
Or use Spring Initializr: `curl https://start.spring.io/starter.zip -d type=gradle-project -d language=java -d bootVersion=3.x -o app.zip`

### ASP.NET Core
```bash
dotnet new webapi -n . --use-controllers
dotnet add package Microsoft.EntityFrameworkCore.SqlServer
```
Then: `dotnet build`

### Flutter
```bash
flutter create .
```
Then write widgets, screens, models, services.
Then: `flutter build` or `flutter analyze`

### React Native (Expo)
```bash
npx create-expo-app@latest . --template blank-typescript
npx expo install react-native-safe-area-context
```
Then: `npx tsc --noEmit`

### Python CLI / Script
```bash
pip install typer rich httpx
```
Then write: `main.py`, `utils.py`, `config.py`
Then: `python -m py_compile main.py`

### Go API
```bash
go mod init app
go get github.com/gin-gonic/gin github.com/jackc/pgx/v5
```
Then write: `main.go`, `handlers/`, `models/`
Then: `go build ./...`

### Rust CLI
```bash
cargo init .
```
Then write: `src/main.rs`, `src/lib.rs`
Then: `cargo check`

## AFTER scaffolding — ALWAYS do this

1. **Install deps**: `npm install` / `pip install` / `composer install` / etc.
2. **Build**: `npm run build` / `python -m compileall` / `dotnet build` / etc.
3. **If build fails**: read the errors, fix the files, rebuild until it passes

## Project structure rules

- Keep related files together in feature folders
- Use barrel exports (`index.ts`) for clean imports
- Add `.env.example` with required environment variables
- Add `README.md` with setup instructions
- Never leave placeholder files or empty directories

## After completing the build

Summarize: what was built, how to run it, and what commands to use.
