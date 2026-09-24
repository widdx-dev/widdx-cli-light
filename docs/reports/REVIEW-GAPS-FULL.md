# تقرير المراجعة الشاملة للفجوات — WIDDX Nexus v3.2.0
**التاريخ**: 4 يوليو 2026  
**المنهجية**: فحص يدوي للكود + تحليل بنية + مراجعة التكوينات + اختبارات الاستيراد  
**الملفات المرجعية**: `GAPS-ANALYSIS.md`، `SCAN-REPORT.md`، `TECHNICAL-ERRORS-REPORT.md`

---

## جدول المحتويات
1. [فجوات حرجة — يجب الإصلاح فوراً](#1-فجوات-حرجة-يجب-الإصلاح-فوراً)
2. [فجوات البنية التحتية](#2-فجوات-البنية-التحتية)
3. [فجوات الكود والتنظيم](#3-فجوات-الكود-والتنظيم)
4. [فجوات التكوين](#4-فجوات-التكوين)
5. [فجوات الاختبارات](#5-فجوات-الاختبارات)
6. [فجوات CI/CD و DevOps](#6-فجوات-cicd-و-devops)
7. [فجوات التوثيق](#7-فجوات-التوثيق)
8. [فجوات Web UI](#8-فجوات-web-ui)
9. [فجوات الأمان](#9-فجوات-الأمان)
10. [فجوات الأداء](#10-فجوات-الأداء)
11. [فجوات التوافقية](#11-فجوات-التوافقية)
12. [فجوات الحزمة والتوزيع](#12-فجوات-الحزمة-والتوزيع)
13. [الملخص وترتيب الأولويات](#13-الملخص-وترتيب-الأولويات)

---

## 1. فجوات حرجة — يجب الإصلاح فوراً

### 1.1 ❌ نصوص التثبيت معطلة بالكامل (HIGH)

| الملف | السطر | يشير إلى | الحالة |
|-------|-------|----------|--------|
| `install.bat` | 3 | `scripts\install.ps1` | **مكسور** — الملف غير موجود |
| `install.ps1` | 6 | `scripts\install.ps1` | **مكسور** — الملف غير موجود |
| `uninstall.bat` | 3 | `scripts\uninstall.ps1` | **مكسور** — الملف غير موجود |
| `uninstall.ps1` | 6 | `scripts\uninstall.ps1` | **مكسور** — الملف غير موجود |

**الملفات المستهدفة `scripts/install.ps1` و `scripts/uninstall.ps1` غير موجودة في المستودع.** تم إزالتها حسب `CHANGELOG.md` v3.2.0 ("Duplicate installation scripts removed") لكن بقيت الـ wrapper files تشير إليها.

**الحل**: إما إنشاء `scripts/install.ps1` و `scripts/uninstall.ps1` أو تعديل الـ wrappers لتشير إلى مسار صحيح.

---

### 1.2 ❌ `core/verification/` يفتقد `__init__.py` (HIGH)

المسار `core/verification/` يحتوي فقط على `loop.py` و `__pycache__/`. لا يوجد `__init__.py`.

هذا يعني أن `from core.verification import ...` سيرفع `ImportError`.

**الحل**: إنشاء `core/verification/__init__.py` يعيد تصدير `VerifyLoop`.

---

### 1.3 ❌ `core/context/__init__.py` — فارغ تماماً (HIGH)

الملف `core/context/__init__.py` حجمه 0 بايت. يحتوي الـ package على 4 وحدات (`hierarchy.py`, `pipeline.py`, `pruner.py`, `rag_integration.py`) لكن لا شيء معاد تصديره.

هذا يعني أن `from core.context import HierarchyCompressor` سيفشل.

**الحل**: إضافة re-exports إلى `core/context/__init__.py`.

---

### 1.4 ❌ مسارات مطلقة في `config.json` (HIGH)

جميع مسارات MCP servers في `config.json` هي مسارات مطلقة على جهاز المطور:

```json
{
  "mcpServers": {
    "filesystem": "/home/widdx/widdx-cli-light/node_modules/...",
    "memory": "/home/widdx/widdx-cli-light/node_modules/...",
    "playwright": "/home/widdx/widdx-cli-light/node_modules/...",
    "sequential-thinking": "/home/widdx/widdx-cli-light/node_modules/..."
  }
}
```

هذا يعني أن WIDDX **لن يعمل أبداً** على أي جهاز آخر بدون تعديل `config.json` يدوياً.

**الحل**: استخدام مسارات نسبية أو متغيرات بيئة (`$PROJECT_ROOT`/`%PROJECT_ROOT%`).

---

### 1.5 ❌ `python -m core` يطلق Web UI بدلاً من CLI (HIGH)

| الأمر | ما يطلق | يتطلب |
|-------|---------|-------|
| `widdx` | CLI (`core/cli.py` → `cli/app.py`) | أساسيات فقط |
| `python main.py` | Web UI (`scripts/web_app:main`) | FastAPI, uvicorn |
| `python -m core` | **Web UI** (`core/__main__.py` → `scripts/web_app:main`) | FastAPI, uvicorn |

`python -m core` يطلق Web UI. إذا كتب المستخدم `python -m core` متوقعاً CLI (لأن `widdx` = CLI)، سيحصل على `ImportError` إذا لم يكن FastAPI مثبتاً.

**الحل**: تغيير `core/__main__.py` لتشغيل CLI مباشرة أو جعله يتيح اختيار الواجهة.

---

## 2. فجوات البنية التحتية

### 2.1 ❌ `requirements.txt` مفقود

ملف `requirements.txt` غير موجود. `Dockerfile` يحاول قراءته بـ `2>/dev/null || true` (يتجاهل الفشل بصمت).

**التأثير**: لا يمكن تثبيت الحزمة عبر `pip install -r requirements.txt`.

### 2.2 ❌ `docker-compose.yml` مفقود

لا يوجد orchestration للـ Docker (مثلاً: web + API + database).

### 2.3 ❌ `.pre-commit-config.yaml` مفقود

لا توجد git hooks للتنسيق الآلي والفحص قبل الـ commit.

### 2.4 ❌ `.editorconfig` مفقود

لا توجد إعدادات محرر متناسقة للمساهمين.

### 2.5 ❌ `CODEOWNERS` مفقود

لا يوجد `CODEOWNERS` أو `.github/CODEOWNERS` للمراجعة التلقائية.

### 2.6 ❌ `SECURITY.md` مفقود

لا توجد سياسة إبلاغ عن الثغرات الأمنية.

---

## 3. فجوات الكود والتنظيم

### 3.1 ❌ كود مهمل/قديم

| الملف | المشكلة |
|-------|---------|
| `core/project_structure.py` | مُعلّم بـ `DeprecationWarning`، مستبدل بـ `project/scanner.py` |
| `core/runtime/gaf/__init__.py` | فارغ تماماً (placeholder) |
| `core/runtime/execution_control_plane.py` | re-export فقط للتوافق العكسي |

### 3.2 ❌ `core/__init__.py` — صادرات مفقودة

وحدات أساسية **غير مصدّرة** علناً رغم وجودها:

| الوحدة | الملف |
|--------|-------|
| `MemoryLearner` | `core/memory_learner.py` |
| `StateManager` | `core/state_manager.py` |
| `SandboxExecutor` | `core/sandbox.py` |
| `VerifyLoop` | `core/verification/loop.py` |
| `CommandGuard` | `core/guard.py` |
| `PatternLibrary` | `core/learning/pattern_library.py` |
| `KnowledgeGraph` | `core/knowledge_graph.py` |

### 3.3 ❌ `github-app/` — دليل يتيم

`github-app/app.py` و `github-app/README.md` موجودان لكن:
- غير مدرجين في `pyproject.toml` packages
- غير مذكورين في Dockerfile
- ليس لهم Makefile target
- ليس لهم CI job

### 3.4 ⚠️ `core/tools/__init__.py` — ترتيب تسجيل هش

السطر 40: `from . import registration` يعدّل `TOOL_DEFINITIONS` بالـ mutation. إذا أعيد استيراد `TOOL_DEFINITIONS` قبل تشغيل `registration.py`، الأدوات ستكون مفقودة.

### 3.5 ⚠️ `scripts/static/REFACTOR-PLAN.md` — في غير مكانه

`REFACTOR-PLAN.md` داخل `scripts/static/` سيتم خدمته كملف static في الإنتاج عند `/static/REFACTOR-PLAN.md`. يجب نقله خارج مجلد static.

---

## 4. فجوات التكوين

### 4.1 ❌ `config.json` — اسم المزود غير صالح

```json
"provider": { "name": "nonexistent-xyz" }
```

`nonexistent-xyz` ليس مزوداً صالحاً. المزودون الصالحون: `ollama`, `gguf`, `opencode-zen`, `opencode`, `deepseek`.

### 4.2 ❌ `core/config/settings.py:20` — `_VALID_PROVIDERS` ينقصه مزودان

```python
_VALID_PROVIDERS = {"ollama", "gguf", "opencode-zen", "opencode", "deepseek"}
```

مفقود: `"openai-compatible"` و `"openai"` — رغم أنهما مزودان صالحان في `provider_factory.py`.

### 4.3 ⚠️ `pyproject.toml` — `all` extra ينقصه تبعيات مهمة

```toml
all = ["widdx-nexus[dev,gguf,voice,gateway]"]
```

مفقود: `api` (FastAPI/uvicorn) و `vision` (Pillow/torch).

يعني `pip install widdx-nexus[all]` لن يثبت web UI ولا الرؤية.

### 4.4 ⚠️ `scripts/web/server.py:1106` vs `web_app.py:50` — افتراضي host غير متطابق

| الملف | افتراضي host |
|-------|-------------|
| `server.py` | `"0.0.0.0"` (معرض للشبكة) |
| `web_app.py` | `"127.0.0.1"` (آمن) |

`web_app.py` يعلّق أن `127.0.0.1` مقصود للأمان، لكن `server.py` افتراضياً يفضح الخادم للشبكة.

---

## 5. فجوات الاختبارات

### 5.1 ❌ وحدات بدون اختبارات

| الوحدة | عدد الأسطر | الخطورة |
|--------|-----------|---------|
| `core/chat.py` | ~300 | معالجة المحادثة الأساسية |
| `core/commands.py` | 771 | 24 أمر slash — لا توجد اختبارات |
| `core/state_manager.py` | ~250 | إدارة الحالة المركزية |
| `core/session_v2.py` | ~200 | إدارة الجلسات |
| `core/skills.py` | ~200 | نظام المهارات |
| `core/workflow.py` | ~300 | محرك سير العمل |
| `core/database.py` | ~200 | طبقة البيانات |
| `core/autonomy_loop.py` | ~150 | الحلقة المستقلة — حرجة جداً |
| `core/self_improve.py` | ~150 | التحسين الذاتي |
| `core/vision.py` | ~350 | نظام الرؤية |
| `core/voice.py` | ~150 | نظام الصوت |
| `core/world_model.py` | ~200 | النموذج السببي |
| `core/gateway/*.py` | ~200 | Telegram + Discord — بدون اختبارات |
| `core/runtime/**/*.py` | ~1000+ | مستوى التحكم الكامل — بدون اختبارات |
| `core/mcp/client.py` | ~300 | عميل MCP |
| `core/evaluation/*.py` | ~400 | التقييم والقياس |
| `core/context/**/*.py` | ~400 | سياق متعدد المستويات |
| `core/plugin_loader.py` | ~150 | تحميل الإضافات |

**إجمالي ~5500 سطر بدون اختبارات.**

### 5.2 ⚠️ اختبارات E2E محدودة

- `test_e2e.py` يختبر فقط استيراد الوحدات (import chain)، لا يختبر تدفقات العمل الفعلية
- لا توجد اختبارات tmux-based
- لا توجد اختبارات تكامل مع LLM حقيقي

### 5.3 ⚠️ `conftest.py` MockProvider محدود

MockProvider الحالي يرد بنص ثابت. لا يحاكي:
- Stream responses
- Tool calls
- Errors/failures
- Multi-turn conversations

---

## 6. فجوات CI/CD و DevOps

### 6.1 ❌ mypy ليس في CI

mypy مهيأ في `pyproject.toml` لكن **لا يعمل في CI**. يمكن دمج كود به type errors دون اكتشاف.

### 6.2 ❌ فحص أمان التبعيات مفقود

لا توجد أدوات مثل `bandit` أو `safety` أو `pip-audit` في CI.

### 6.3 ❌ ruff لا يفحص جميع المجلدات

```yaml
- run: ruff check core/
```

`cli/` و `tui/` و `scripts/` غير مشمولة في فحص ruff.

### 6.4 ⚠️ CI `widdx --version` يفشل بصمت

```yaml
- run: widdx --version
```

`core/cli.py:run()` لا يعالج `--version`. الأمر سيفشل لكن CI لن يكتشفه (exit code غير محدد).

### 6.5 ⚠️ CI لا يختبر Python 3.13

المصفوفة: `3.10, 3.11, 3.12` — وليس `3.13`.

`pyproject.toml` classifiers أيضًا لا تتضمن `3.13`.

### 6.6 ❌ Dockerfile يثبت dev dependencies في صورة الإنتاج

```dockerfile
RUN pip install -e ".[dev]"
```

`dev` تشمل `pytest`, `twine`, `build` — هذه ليست ضرورية في الإنتاج وتزيد حجم الصورة.

### 6.7 ❌ Dockerfile يفتقد `.dockerignore`

بدون `.dockerignore`، سيتم نسخ:
- `.mypy_cache/`, `.ruff_cache/` (مئات الملفات)
- `.widdx/` (بيانات محلية، DB)
- `.git/` (التاريخ الكامل)
- `node_modules/` (تبعيات MCP)
- `build/` (artifacts سابقة)

### 6.8 ❌ `build/lib/` — artifacts بناء في git

`build/lib/` يحتوي على نسخة كاملة من الحزمة المترجمة. هذا artifact بناء يجب أن يكون في `.gitignore`.

### 6.9 ❌ `.mypy_cache/` و `.ruff_cache/` و `*.egg-info/` — tracked

هذه المجلدات في شجرة العمل. وإن كانت في `.gitignore`، فوجودها يشير إلى أن git clean غير منتظم.

---

## 7. فجوات التوثيق

### 7.1 ⚠️ `CONTRIBUTING.md` — ينقصه تفاصيل

- يذكر 539 اختباراً لكن لا يذكر `make test` يستخدم `-k "not test_next_run_daily"`
- لا يذكر إعداد `.env` أو API keys للتطوير
- لا يذكر conventions للـ commit messages (scoping)
- لا يذكر كيفية إضافة skill جديد

### 7.2 ⚠️ `README.md` — ينقصه تفاصيل

- لا يذكر `widdx-tui` command
- لا يذكر `widdx-api` command
- لا يذكر متطلبات Node.js لـ MCP servers
- يذكر `config.json` دون توضيح أنه يحتاج تعديل

### 7.3 ❌ لا يوجد video tutorials أو interactive tutorials

المقارنة: OpenCode لديه video tutorials متعددة.

### 7.4 ❌ لا يوجد documentation website مخصص

التوثيق فقط في ملفات Markdown داخل المستودع.

---

## 8. فجوات Web UI

### 8.1 ❌ لا يوجد `favicon.ico`

`/favicon.ico` يرجع `204 No Content`. الملف غير موجود في `scripts/static/`.

### 8.2 ❌ لا يوجد PWA manifest

لا `manifest.json` ولا service worker (`sw.js`). لا يمكن تثبيت Web UI كـ PWA.

### 8.3 ⚠️ `scripts/static/js/` — 26 ملف JS بدون build tooling

لا ESLint، لا Prettier، لا bundler (webpack/vite). JS يخدم مباشرة كلوحة HTML.

### 8.4 ⚠️ WebSocket timeout طويل (600s)

`core/chat.py` يستخدم timeout 600 ثانية (10 دقائق). يُفضل 120 ثانية.

---

## 9. فجوات الأمان

### 9.1 ❌ Sandbox محدود على Windows

`preexec_fn` (المستخدم لعزل العمليات) متاح فقط على Unix. Windows ليس له equivalent.

### 9.2 ⚠️ 56 bare `except:` blocks

```python
except:
    pass
```

هذه تخفي الأخطاء. معظمها في:
- `core/state_manager.py` — 10 matches
- `core/uil/brain.py` — 10 matches
- `core/mcp/client.py` — 8 matches
- `core/agents/agent.py` — 7 matches

### 9.3 ⚠️ XOR obfuscation لـ API keys

`core/config/keychain.py` يستخدم XOR بسيط لتخزين API keys. هذا ليس تشفيراً حقيقياً — أي شخص لديه وصول للملف يمكنه فك تشفير المفتاح.

### 9.4 ⚠️ `core/tools/security.py` غير مُصدّر

دالة `scan_dangerous()` موجودة لكنها ليست في `core/tools/__init__.py` العام. لا توجد طريقة عامة للوصول إليها أو اختبارها.

### 9.5 ❌ لا يوجد فحص أمان تلقائي للتبعيات

لا `bandit` ولا `safety` ولا `pip-audit` مهيأة.

---

## 10. فجوات الأداء

### 10.1 ❌ KnowledgeGraph بدون caching

`knowledge_graph.py` يبني الرسم البياني من الصفر في كل مرة باستخدام `rglob("*")`. للمشاريع الكبيرة (10K+ ملف) هذا قد يستغرق دقائق.

### 10.2 ⚠️ `rglob("*")` في 14 ملف مختلف

نفس pattern يتكرر في `repo_mapper.py`, `project/scanner.py`, `memory.py`, إلخ. كلها تمسح جميع الملفات في جميع المجلدات الفرعية.

### 10.3 ❌ لا يوجد log rotation

ملف `widdx-tui.log` (الموجود في شجرة العمل) ينمو بدون حدود. لا rotate ولا max size ولا max backup.

### 10.4 ⚠️ StateManager cache قصير (2s)

`state_manager.py:38` cache لمدة 2 ثانية فقط. للمشاريع الكبيرة، هذا يعني إعادة بناء السياق باستمرار.

### 10.5 ❌ لا يوجد parallel file reading

عند قراءة ملفات متعددة (مثل `memory.py` في loop)، القراءة متسلسلة. استبدال بـ `concurrent.futures.ThreadPoolExecutor` يمكن أن يحسن الأداء.

---

## 11. فجوات التوافقية

### 11.1 ❌ Python 3.13 غير مدعوم

- `pyproject.toml` classifiers: `3.10, 3.11, 3.12`
- CI matrix: `3.10, 3.11, 3.12`
- الكود يستخدم `match/case` (Python 3.10+) وهو متوافق مع 3.13

### 11.2 ⚠️ Node.js prerequisite غير موثّق

MCP servers تعتمد على Node.js لكن هذا غير مذكور في README أو أي متطلبات تثبيت.

### 11.3 ⚠️ Type hints غير كاملة

نحو 50% من الدوال العامة تفتقد type hints. هذا يقلل من:
- IDE autocompletion
- Static analysis (mypy)
- Readability

---

## 12. فجوات الحزمة والتوزيع

### 12.1 ❌ `all` extra غير مكتمل

```toml
all = ["widdx-nexus[dev,gguf,voice,gateway]"]
```

مفقود: `api` (لتشغيل web server) و `vision`.

### 12.2 ⚠️ `github-app` خارج الحزمة

الدليل `github-app/` ليس في `pyproject.toml packages`. لا يمكن تثبيته عبر pip.

### 12.3 ❌ لا يوجد `requirements.txt`

الاعتماد الوحيد على `pyproject.toml` يجعل التثبيت عبر `pip install -r requirements.txt` مستحيلاً.

### 12.4 ⚠️ egg-info في git

`widdx_nexus.egg-info/` في شجرة العمل (وإن كان gitignored). هذا artifact بناء.

---

## 13. الملخص وترتيب الأولويات

### 🔴 أولوية حرجة (تُصلح فوراً)

| # | الفجوة | الجهد |
|---|--------|-------|
| 1 | نصوص التثبيت الأربعة معطلة | 30 دقيقة |
| 2 | `core/verification/` يفتقد `__init__.py` | 5 دقائق |
| 3 | `core/context/__init__.py` فارغ | 10 دقائق |
| 4 | مسارات مطلقة في `config.json` | 30 دقيقة |
| 5 | `python -m core` يطلق Web UI | 15 دقيقة |
| 6 | `config.json` provider name غير صالح | 1 دقيقة |
| 7 | `all` extra ينقصه `api` و `vision` | 5 دقائق |
| 8 | Dockerfile يثبت dev dependencies | 10 دقائق |
| 9 | Dockerfile يفتقد `.dockerignore` | 10 دقائق |

### 🟡 أولوية عالية (تُصلح خلال أسبوع)

| # | الفجوة | الجهد |
|---|--------|-------|
| 10 | 28+ وحدة بدون اختبارات | 2-4 أسابيع |
| 11 | mypy ليس في CI | يوم واحد |
| 12 | ruff لا يفحص `cli/` `tui/` `scripts/` | 30 دقيقة |
| 13 | `build/lib/` و cache artifacts في git | 30 دقيقة |
| 14 | `_VALID_PROVIDERS` ينقصه مزودان | 5 دقائق |
| 15 | `scripts/static/REFACTOR-PLAN.md` في غير مكانه | 5 دقائق |
| 16 | 56 bare `except:` blocks | يوم واحد |
| 17 | KnowledgeGraph يحتاج caching | 2-3 أيام |
| 18 | StateManager cache قصير (2s) | 30 دقيقة |

### 🟢 أولوية متوسطة (شهر)

| # | الفجوة | الجهد |
|---|--------|-------|
| 19 | `requirements.txt` مفقود | يوم واحد |
| 20 | `.pre-commit-config.yaml` مفقود | يوم واحد |
| 21 | `.editorconfig` مفقود | 30 دقيقة |
| 22 | `CODEOWNERS` مفقود | 30 دقيقة |
| 23 | `SECURITY.md` مفقود | ساعتان |
| 24 | `docker-compose.yml` مفقود | يوم واحد |
| 25 | لا PWA ولا service worker | 2-3 أيام |
| 26 | لا log rotation | يوم واحد |
| 27 | `github-app/` يتيم | 2-3 أيام |
| 28 | Python 3.13 غير مدعوم | يوم واحد |
| 29 | `CONTRIBUTING.md` ينقصه تفاصيل | يوم واحد |

### 🔵 أولوية منخفضة (شهران)

| # | الفجوة | الجهد |
|---|--------|-------|
| 30 | فحص أمان تلقائي (bandit/safety) | يومان |
| 31 | E2E tests (tmux-based) | 2-4 أسابيع |
| 32 | Video tutorials | مستمر |
| 33 | Documentation website | 2-4 أسابيع |
| 34 | Windows Sandbox equivalent | 2-4 أسابيع |
| 35 | XOR obfuscation → تشفير حقيقي | 2-3 أيام |
| 36 | parallel file reading | 2-3 أيام |

---

### إجمالي الفجوات المكتشفة: **36 فجوة** (9 حرجة، 9 عالية، 11 متوسطة، 7 منخفضة)

هذا التقرير يركز على الفجوات **الجديدة** التي لم تغطها التقارير السابقة (`GAPS-ANALYSIS.md`، `SCAN-REPORT.md`، `TECHNICAL-ERRORS-REPORT.md`). الفجوات المتعلقة بالمقارنة مع OpenCode/Codebuff (Desktop App, Agent Store, i18n, one-line install, Discord community) موثقة بشكل جيد في `GAPS-ANALYSIS.md` ولا تتكرر هنا.

**التوصية**: التركيز على الـ 9 فجوات الحرجة أولاً (جهد إجمالي ~ساعتان)، ثم الـ 9 عالية الأولوية (جهد إجمالي ~أسبوع-أسبوعين).
