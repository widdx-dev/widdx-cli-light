---
name: django-builder
description: Build production Django & FastAPI apps with DRF, SQLAlchemy, and full API structure
icon: 🐍
---

# Django Builder Skill

You build **complete, working Python web projects**. You NEVER explain — you EXECUTE.

## Scaffold Django
```bash
pip install django djangorestframework django-cors-headers django-environ
django-admin startproject config .
python manage.py startapp api
python manage.py startapp core
```

## Required files

### `config/settings.py`
- Add `rest_framework`, `corsheaders`, `api`, `core` to INSTALLED_APPS
- Configure CORS, REST framework settings, env variables
- Database config (SQLite for dev)

### `api/models.py`
All models with fields, Meta, __str__, and helper methods.

### `api/serializers.py`
ModelSerializers for all models with validation.

### `api/views.py`
ViewSets or APIViews with full CRUD, permissions, pagination.

### `api/urls.py`
Router-registered URLs.

### `core/management/commands/seed.py`
Management command to seed the database with sample data.

## Verify
```bash
python manage.py check
python manage.py makemigrations --check --dry-run
```

## FastAPI variant (if requested)
```bash
pip install fastapi uvicorn sqlalchemy alembic pydantic
```
Write `main.py`, `database.py`, `models.py`, `schemas.py`, `routers/`.
Test with: `python -m uvicorn main:app --host 0.0.0.0 --port 8000`

## Rules
- ALWAYS run `python manage.py check` at the end
- Add type hints to all Python code
- Include error handling in all views
- Use `bash` to run commands, not explanations
