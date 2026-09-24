---
name: flutter-builder
description: Build production Flutter & React Native (Expo) mobile apps with full architecture
icon: 📱
---

# Flutter Builder Skill

You build **complete, working mobile apps**. You NEVER explain — you EXECUTE.

## Scaffold Flutter
```bash
flutter create . --org com.app --platforms android,ios
```

## Required directories & files

### `lib/main.dart`
MaterialApp with theme, routes, providers.

### `lib/app/` — App config
- `theme.dart` — light/dark themes
- `routes.dart` — named routes
- `dependencies.dart` — dependency injection

### `lib/screens/` — Full screens
With Scaffold, AppBar, body, floating actions.

### `lib/widgets/` — Reusable widgets
Custom buttons, cards, inputs, loading states.

### `lib/models/` — Data models
With fromJson/toJson, copyWith.

### `lib/services/` — API & data services
HTTP client, local storage, error handling.

### `lib/providers/` or `lib/bloc/` — State management
Using Provider, Riverpod, or Bloc pattern.

### `lib/utils/` — Helpers
Validators, formatters, constants.

### `pubspec.yaml`
Add dependencies: http, provider/riverpod, shared_preferences, cached_network_image, flutter_secure_storage.

## Verify
```bash
flutter analyze
```

## React Native (Expo) variant (if requested)
```bash
npx create-expo-app@latest . --template blank-typescript
npx expo install react-native-safe-area-context expo-router
```
Write `app/` directory with file-based routing, components, screens.
Verify: `npx tsc --noEmit`

## Rules
- Always handle loading, error, empty states
- Use const constructors where possible
- Follow the framework's naming conventions
- ALWAYS run `flutter analyze` before declaring done
- Use `bash` to run commands, not explanations
