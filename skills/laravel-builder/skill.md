---
name: laravel-builder
description: Build production Laravel apps with Breeze, Livewire, Eloquent, and tests
icon: 🧙
---

# Laravel Builder Skill

You build **complete, working Laravel projects**. You NEVER explain — you EXECUTE.

## Scaffold Laravel
```bash
composer create-project laravel/laravel .
```

## Install additional packages (if needed)
```bash
composer require laravel/breeze
php artisan breeze:install blade
npm install && npm run build
```

## Required files to write

### Routes (`routes/web.php`)
All web routes with named routes, controller references.

### Controllers (`app/Http/Controllers/`)
Full controllers with validation, error handling, responses.

### Models (`app/Models/`)
With fillable/guarded, relationships, casts.

### Migrations (`database/migrations/`)
With proper schema, indexes, foreign keys.

### Views (`resources/views/`)
Blade templates with layout, components, forms.

### Config (`config/`)
Any custom config files needed.

## Database setup
```bash
php artisan migrate
```

## Verify
```bash
php artisan route:list
php artisan config:clear
composer run-script lint 2>/dev/null || echo "no lint"
```

## Rules
- ALWAYS run `php artisan migrate` after creating migrations
- ALWAYS add validation to form requests
- NEVER leave placeholder routes
- Use `bash` to run artisan commands, not explanations
