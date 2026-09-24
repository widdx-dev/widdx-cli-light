# WIDDX Web UI — خطة التطوير الشاملة

## نظرة عامة

تطوير واجهة `scripts/static/` عبر 4 مراحل كبرى: تنظيف ← تمكين ← Canvas ← نظام متكامل.

---
## ✅ المرحلة 1: التطهير — مكتملة

**الهدف**: نفس الواجهة، كود نظيف وآمن.

### XSS → DOMPurify
- `parseMarkdown()`: اعادة ترتيب — `escapeHtml()` على المجموعات أولاً ← `DOMPurify.sanitize()` على HTML النهائي
- منع تجاوزات: `javascript:` URI (مع line-break `\n`)، `data:text/html`، onload/onerror/onclick في `_sanitizeHtml()`
- `data-click` لنسخ الكود/المسار بدلاً من onclick المباشر

### God Object S → S.chat / S.ui / S.stream
- Proxy في `nexus.js` للتوافق العكسي
- `S.chat`: messages, model, tokens
- `S.ui`: activity, theme, view
- `S.stream`: ws, streaming, _activeThinking, _activeToolCard

### View Registry
- `const VIEWS = { chat, dashboard, settings, ... }` — إزالة 25+ if/else في `showView()`

### onclick → data-click + CLICK_HANDLERS
- 62 onclick في `index.html` → `data-click` أو `addEventListener`
- ~85 onclick في `js/` → `CLICK_HANDLERS` + `data-click`
- 4 `.onclick =` → `addEventListener`
- 0 onclick نشط في التطبيق

### Inline styles → CSS classes
- ~130 inline style حوّلت إلى كلاسات CSS
- ~50 كلاس CSS جديد (`.flex-ac`, `.gap-8`, `.btn-icon-*`, `.text-*`, وغيرها)
- الـ 128 المتبقية ديناميكية/متغيرات/display:none

### تحسينات داخلية إضافية
- **PALETTE_ACTIONS registry**: 30+ switch/case ← object lookup
- **IntersectionObserver**: scrollMonitor setInterval(3s) ← Observer
- **Style.css**: كلاسات جديدة + .scroll-sentinel

---
## ✅ المرحلة 2: التمكين — مكتملة

**الهدف**: المستخدم يفتح ويعدّل ويشغّل ويشاهد — دون مغادرة.

### File Explorer
| الميزة | الوصف |
|--------|-------|
| شجرة expand/collapse | ضغط ▶ يوسع المجلد inline بدون إعادة تحميل، مستوى indent حتى 8 |
| بحث فوري | input في toolbar مع فلتر visibility فوري |
| قائمة يمين (Context Menu) | Open, Rename, Copy Path, Delete |
| Delete inline | زر ✕ يظهر عند Hover على كل عنصر |
| Breadcrumbs |导航 المسار مع click على أي جزء |
| refresh / new file / new folder | أزرار في toolbar |

### File Editor
| الميزة | الوصف |
|--------|-------|
| CodeMirror 5 | syntax highlighting لـ 8 لغات (JS, Python, HTML, CSS, Markdown, YAML, Shell, SQL) |
| Auto-detect language | من امتداد الملف |
| Monokai theme | يتوافق مع الوضع الليلي |
| Auto-save | save بعد 2 ثانية من آخر تغيير (debounced) |
| Ctrl+S | حفظ يدوي |
| Run button | يشغّل الملف حسب امتداده (python3/node/bash...) |
| Line numbers | ترقيم الأسطر |
| Auto-preview HTML | HTML files → iframe preview تلقائي |

### Process Manager
| الميزة | الوصف |
|--------|-------|
| قائمة عمليات | PID, name, CPU, Memory, Status dot |
| Kill | زر لكل عملية |
| Live auto-refresh | كل 5 ثوانٍ بدون إعادة تحميل كامل |
| Toggle live | زر ● Live لتشغيل/إيقاف التحديث التلقائي |

### Preview iframe
| الميزة | الوصف |
|--------|-------|
| Browser tab | عرض iframe مع URL input |
| Go button | تحميل URL في iframe |
| Refresh | زر إعادة تحميل الصفحة |
| Live toggle | auto-refresh كل 3 ثوانٍ (للمواقع الخارجية فقط) |
| HTML preview | إنشاء Blob URL من HTML المحرر وعرضه تلقائياً |

### الملفات التي تغيرت في المرحلتين 1+2
- `index.html` — +CodeMirror CDN، إزالة onclick
- `nexus.js` — CLICK_HANDLERS, File Explorer, Editor, Process, Browser, S Proxy
- `ui.js` — PALETTE_ACTIONS, suggestion chips
- `style.css` — ~50 utility كلاس، كلاسات File Explorer/Editor/Context Menu الجديدة
- `views/*.js` (15 ملف) — onclick→data-click، inline styles→classes

---
## ✅ المرحلة 3: Canvas الذكي — مكتملة

**الهدف**: AI ينتج أي محتوى، Canvas يعرضه تفاعلياً وبذكاء.

### النظام
| المكون | الوصف |
|--------|-------|
| **__analyzeContent** | محلل عميق: headings, word count, code ratio, table ratio, headWords, sigStrength, 15+ signal detectors |
| **Score-based Dispatcher** | كل Canvas يُسجّل score، `__lenFactor()` يعدّل حسب طول المحتوى، الأعلى يفوز |
| **Smart Fallback** | أي محتوى لا يطابق Canvas يحصل على تحسينات: headings مرقّمة، جداول، code blocks، checkboxes |

### 12 Canvas Type

| النوع | الكشف | العرض |
|-------|-------|-------|
| **Document** | ≥2 headings + ≥100 words | TOC جانبي مع scroll، headings مع anchor IDs |
| **Table** | ≥1 جدول | جداول محسّنة مع hover/stripe، أولوية للمقارنات |
| **Code** | code blocks ≥ 20% من المحتوى | language label + ترقيم لكل بلوك |
| **Travel** | Day N + itinierary keywords | تلوين Day markers، أيقونات مواقع |
| **Comparison** | vs/versus + pros/cons | تلوين أخضر/أحمر للجداول والنقاط |
| **Glossary** | ≥3 **term**: definition | بطاقات term-definition منظمة |
| **Timeline** | سنوات في بداية السطور | خط عمودي مع نقاط زمنية |
| **Tasks** | - [ ] / - [x] | Checkboxes تفاعلية مع ✅/⬜ |
| **Architecture** | system/architecture keywords + headings | بطاقات مكونات مع language labels |
| **FAQ** | ≥4 Q:/A: patterns | تنسيق Q&A مع لون خلفية مميز |
| **Changelog** | version numbers + dates | تلوين الإضافات (✨) والإصلاحات (🐛) والتغييرات (🔄) |
| **Recipe** | ingredients + steps + time | تنسيق المكونات والخطوات |

### Canvas CSS
- ~300 سطر CSS ديناميكي يُحقن تلقائياً
- responsive للشاشات الصغيرة (mobile ≤820px)
- كل Canvas له تنسيق مستقل (glossary cards, timeline line, FAQ bubbles, etc.)

### التكامل
- يُفعّل بعد `finishThinking()` (اكتمال البث)
- يحلل المحتوى كاملاً←يختار Canvas←يستبدل HTML
- لا يؤثر على البث المباشر، فقط على العرض النهائي

### الملفات التي تغيرت
- `nexus.js` — +450 سطر (Canvas system)
- `index.html` — بدون تغيير (CSS يُحقن ديناميكياً)

---
## ✅ المرحلة 4: النظام — مكتملة

**الهدف**: Git panel كامل، Dashboard مباشر، حفظ/تصدير.

### Git Panel
| الميزة | الوصف |
|-------|--------|
| **Status** | عرض current branch, files changed (M/A/D/?), ahead/behind |
| **Staging** | Checkboxes لكل ملف مع staging |
| **Commit** | Message input + Commit مع auto-commit fallback |
| **Push/Pull** | أزرار للـ remote operations |
| **Branches** | عرض + إنشاء + Switch بين الفروع |
| **Diff Viewer** | عرض الفروقات لكل ملف |
| **History** | Commit log مع hashes |
| **CLICK_HANDLERS** | 7 handlers + event delegation للـ switch/diff |

### Dashboard
| الميزة | الوصف |
|-------|--------|
| **Live stats** | Platform, Sandbox, Agents, Cron, Git, Tokens — كلها تتحدّث |
| **Auto-refresh** | كل 10 ثوانٍ بدون إعادة تحميل |
| **Resource bars** | CSS bars متحركة لـ agents/bg/skills/cron/memory |
| **Activity feed** | آخر 10 active events |
| **Gateway** | حالة القنوات المتصلة |
| **Error recovery** | Retry button + silent refresh |

### Export System
| الميزة | الوصف |
|-------|--------|
| **Export dialog** | واجهة اختيار: Markdown (نسخ)، .md (تحميل)، .json (تحميل) |
| **Markdown export** | تنسيق مع header + timestamps + فواصل |
| **JSON export** | هيكل كامل مع metadata (model, count, timestamp) |
| **Palette integration** | أمر Export في command palette |

---
## خريطة التنفيذ

```
المرحلة 1: التطهير       ✅━━━━━━━━━━━━━━━━━━━━━ 100%
المرحلة 2: التمكين       ✅━━━━━━━━━━━━━━━━━━━━━ 100%
المرحلة 3: Canvas        ✅━━━━━━━━━━━━━━━━━━━━━ 100%
المرحلة 4: النظام        ✅━━━━━━━━━━━━━━━━━━━━━ 100%
```

---
*آخر تحديث: 1 يوليو 2026*
