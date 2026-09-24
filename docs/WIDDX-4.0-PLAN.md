# WIDDX 4.0 — الخمس قدرات المتقدمة

> التاريخ: 2026-06-26 | الحالة: Planning  
> الهدف: تجاوز مرحلة "مساعد برمجي" إلى "منصة وكلاء هندسية"

---

## قوانين البناء

### القانون 1: لا تكسر شيئاً
- 508 اختبار يجب أن تبقى 507+ ناجحة بعد كل commit
- أي تغيير في core/ يجب أن يكون له اختبار
- لا تعدّل توقيعات الدوال العامة إلا إذا كان هناك سبب قوي

### القانون 2: اعتمد على الموجود
- لا تنشئ ملفاً جديداً إلا إذا كان ضرورياً
- استخدم الأنماط الموجودة (singleton, dataclass, lazy import)
- كل قدرة جديدة تبني على ما هو موجود

### القانون 3: كود نظيف
- type hints على كل public API
- docstring لكل class و public method
- لا bare except: — استخدم أنواع محددة
- no print() — استخدم logging
- imports في أعلى الملف

### القانون 4: كل قدرة تُختبر
- module جديد → test_xxx.py جديد
- القدرة الجديدة يجب أن يكون لها اختبار واحد على الأقل
- الاختبار يجب أن يتحقق من السلوك وليس مجرد import

### القانون 5: الواجهة الخلفية أولاً، الأمامية ثانياً
- core/ أولاً مع اختبارات
- ثم scripts/web/ للتوصيل
- أخيراً static/js/ للـ Web UI

---

## الخمس قدرات — خطة التنفيذ

### 1. Verification Engine (Verify → Fix → Retest Loop)

**الهدف:** لا يثق الـ Agent في نجاح المهمة حتى يثبت بالاختبارات.

**الملفات الجديدة:**
- `core/verification/loop.py` — `VerifyLoop` class
  - `verify(output, task_type) → list[Finding]`
  - `attempt_fix(finding, context) → bool`
  - `run_loop(output, task_type, max_retries=3) → VerifyResult`

**الملفات المعدلة:**
- `core/uil/brain.py` — استدعاء `VerifyLoop.run_loop()` بدلاً من verifier واحد

**الاختبارات:**
- `tests/test_verification_loop.py` — fix → retest → pass cycle

**المنطق:**
```
Execute → Verify → if CRITICAL errors:
  Fix → Re-verify → if still CRITICAL:
    Fix again → Re-verify → if still CRITICAL:
      Return with errors flagged
```

---

### 2. Knowledge Graph

**الهدف:** فهم المشروع كـ graph وليس نصوصاً متفرقة.

**الملفات الجديدة:**
- `core/knowledge_graph.py` — `KnowledgeGraph` class
  - nodes: files, classes, functions, tables, APIs
  - edges: imports, calls, inherits, references, depends_on
  - `build(project_dir) → graph`
  - `query(entity_name) → list[related]`
  - `find_path(from_entity, to_entity) → list[edges]`

**الملفات المعدلة:**
- `core/repo_mapper.py` — يستخدم `KnowledgeGraph` داخلياً
- `core/uil/brain.py` — يحقن graph context في system prompt

**الاختبارات:**
- `tests/test_knowledge_graph.py`

**المكونات المعاد استخدامها:**
- `RepoMapper._extract_python()` — استخراج symbols موجود
- `ProjectScanner.scan()` — تعداد الملفات موجود

---

### 3. Memory Versioning

**الهدف:** كل معلومة لها عمر افتراضي، ثقة، وحالة.

**الملفات المعدلة:**
- `core/memory.py` — `MemoryStore.save()` تضيف version, timestamp, confidence, status

**الهيكل الجديد للـ frontmatter:**
```yaml
---
name: fix-sql-connection-pool
description: Use connection pool for SQLite
metadata:
  type: learned_fix
  version: 1
  confidence: 0.8
  status: active       # active | deprecated | superseded
  superseded_by: ~
  created: 2026-06-26T10:00:00
  last_validated: 2026-06-26T12:00:00
---
```

**الدوال الجديدة:**
- `MemoryStore.search_active(query)` — يستبعد deprecated
- `MemoryStore.deprecate(name, reason)` — يعلم كـ deprecated
- `MemoryStore.validate(name)` — يحدث `last_validated`
- `MemoryStore.cleanup_deprecated(older_than_days=90)` — يحذف القديم

---

### 4. Architecture Decision Records (ADR)

**الهدف:** تسجيل كل قرار هندسي مع سببه، بدائله، وعواقبه.

**الملفات الجديدة:**
- `core/adr.py` — `ADRManager` class
  - `record(title, context, decision, alternatives, consequences) → adr_id`
  - `search(query) → list[ADR]`
  - `get_context_for_prompt() → str` — يحقن في system prompt

**صيغة الملف:** `.widdx/adr/{id}-{slug}.md`

**الاختبارات:**
- `tests/test_adr.py`

**التكامل:**
- ADR يُحقن في system prompt لمنع اقتراح حلول سبق رفضها
- عندما يسأل Agent عن تقنية، يبحث في ADR أولاً

---

### 5. Automatic Documentation Sync

**الهدف:** اكتشاف الفروقات بين الكود والوثائق وتحديثها.

**الملفات الجديدة:**
- `core/doc_sync.py` — `DocSync` class
  - `detect_drift(project_dir) → list[DriftWarning]`
  - `auto_update_docs(warnings) → list[updated]`
  - `run_periodically()` — تشغيل كل 30 دقيقة

**المنطق:**
```
1. اقرأ كل وثائق .widdx/
2. اقرأ الكود الفعلي
3. قارن:
   - APIs المذكورة في DESIGN.md هل ما زالت موجودة؟
   - المهام في TASKS.md المعلّمة ✅ هل الكود يعكسها؟
   - المكتبات في ROADMAP.md هل تُطابق imports الكود؟
4. ولّد DriftWarning لكل اختلاف
5. Agent يقرر: auto-fix أو notify user
```

**الاختبارات:**
- `tests/test_doc_sync.py`

---

## ترتيب التنفيذ

| # | القدرة | الوقت | التأثير | التعقيد |
|---|--------|-------|--------|--------|
| 1 | Memory Versioning | 30min | Medium | Low |
| 2 | ADR | 1h | High | Low |
| 3 | Verification Loop | 2h | Critical | Medium |
| 4 | Knowledge Graph | 2h | High | High |
| 5 | Auto Doc Sync | 1.5h | Medium | Medium |

**المجموع: ~7 ساعات**

---

## Verification النهائي

بعد كل قدرة:
1. `pytest tests/ -q` — لا فشل جديد
2. `python -c "import core.xxx"` — import نظيف
3. `widdx-web` — Web UI يشتغل
4. commit منفصل لكل قدرة
