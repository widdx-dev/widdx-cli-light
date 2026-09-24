# WIDDX Nexus — خطة إصلاح شاملة (من اختبار اللعبة)

> تم الاكتشاف عبر: بناء Snake game في `E:\deepseek\test2` عبر واجهة Web UI  
> عدد المشاكل: 12 | الوقت المتوقع: 8-10 ساعات

---

## 🔴 P0 — Critical (تمنع الاستخدام)

### 1. Permission NORMAL يعطل أدوات Agent في Web UI
**الملف:** `core/permissions.py` + `scripts/web/chat.py`  
**المشكلة:** Agent يستخدم `write`/`bash` → permission NORMAL يطلب تأكيد → لا يوجد stdin في WebSocket → الـ Agent يعلق للأبد.  
**الإصلاح:** في `ChatHandler`، اضبط permission إلى PERMISSIVE عند تشغيل agent عبر WebSocket، أو أضِف WebSocket-based permission prompt.

### 2. زر Stop لا ينظف حالة Agent بشكل كامل
**الملف:** `scripts/static/js/nexus.js`  
**المشكلة:** بعد الضغط على Stop، يظهر "Cancelled" لكن زر Stop يبقى مرئياً، وحالة "Thinking" لا تختفي.  
**الإصلاح:** دالة `cancelAgent()` يجب أن تعيد ضبط جميع حالات UI (إخفاء Stop، إظهار Send، تعيين status إلى Ready).

---

## 🟡 P1 — High (تؤثر على تجربة المستخدم)

### 3. لا يوجد Permission Prompt في Web UI
**الملف:** `scripts/web/server.py` + `scripts/static/js/nexus.js`  
**المشكلة:** عندما يطلب permission، لا توجد نافذة تأكيد في Web UI. المستخدم لا يعرف أن الأداة معلقة.  
**الإصلاح:** WebSocket event `tool_permission_required` → UI يعرض modal بتفاصيل الأداة + أزرار [Allow] [Deny] [Always].

### 4. Streaming stuck — "Thinking" مع استجابة جزئية
**الملف:** `core/uil/brain.py` + `core/chat.py`  
**المشكلة:** Autonomous agent يبدأ streaming ثم يتوقف عند `write` tool call. يظهر "Thinking" للأبد.  
**الإصلاح:** إضافة timeout في AutonomousAgent (5 دقائق كحد أقصى لكل turn). إذا تجاوز، kill الـ agent وأرسل رسالة خطأ.

### 5. نص Stop button placeholder يظهر عند غير الحاجة
**الملف:** `scripts/static/index.html` + `scripts/static/js/nexus.js`  
**المشكلة:** زر Stop يظهر في Dashboard و Settings views. يجب أن يظهر فقط في Chat view أثناء streaming.  
**الإصلاح:** إخفاء زر Stop عند تبديل الـ view وإظهاره فقط عند بدء streaming.

### 6. Voice input — لا توجد تشويحات أو رسائل خطأ
**الملف:** `scripts/static/js/nexus.js` — دالة `toggleVoiceInput()`  
**المشكلة:** بدون ميكروفون، لا توجد رسالة خطأ مرئية. زر الميكروفون يتغير لونه للأحمر فقط.  
**الإصلاح:** إضافة `showToast()` لرسائل الخطأ/النجاح. دعم المتصفحات بدون Web Speech API.

---

## 🔵 P2 — Medium (تحسينات وظيفية)

### 7. Project Docs تُنشأ فارغة للمشاريع الجديدة
**الملف:** `core/project_tracker.py` — `ensure_docs()`  
**المشكلة:** النماذج تُنشأ لكن بمحتوى فارغ. يجب أن تحتوي على محتوى مفيد افتراضي.  
**الإصلاح:** `ensure_docs()` تولد محتوى مبدئي بقالب احترافي مع تعليمات للمستخدم.

### 8. Terminal — لا يوجد history أو autocomplete
**الملف:** `scripts/static/js/nexus.js`  
**المشكلة:** الـ Terminal لا يحفظ الأوامر السابقة ولا يدعم Tab completion.  
**الإصلاح:** إضافة history array + arrow key navigation.

### 9. Image/File upload — لا يوجد preview
**الملف:** `scripts/static/js/nexus.js` — دالة `handleImageUpload()`, `handleFileUpload()`  
**المشكلة:** بعد اختيار صورة أو ملف، لا يظهر preview في الـ chat input area. المستخدم لا يعرف أن الملف جاهز.  
**الإصلاح:** إضافة thumbnail/اسم ملف في input area بعد الاختيار.

---

## ⚪ P3 — Low (تحسينات تجميلية)

### 10. favicon.ico — 404
**الإصلاح:** إضافة favicon بسيط في `/static/favicon.ico`.

### 11. Console warning: password field not in form
**الملف:** `scripts/static/index.html` — Settings view  
**الإصلاح:** تغليف input كلمة المرور في `<form>` tag.

### 12. Quick Terminal buttons — لا تظهر نتيجة فورية
**الملف:** `scripts/static/js/nexus.js`  
**المشكلة:** عند الضغط على `dir` button، الأمر يُرسل لكن النتيجة لا تظهر حتى ينتهي الـ streaming.  
**الإصلاح:** تنفيذ الأوامر السريعة مباشرة بدون streaming.

---

## Priority Summary

| # | Severity | Issue | Effort |
|---|----------|-------|--------|
| 1 | P0 | Permission يعطل agent tools | 2h |
| 2 | P0 | Stop button لا ينظف UI | 1h |
| 3 | P1 | لا يوجد permission prompt في Web | 3h |
| 4 | P1 | Streaming stuck timeout | 1h |
| 5 | P1 | Stop button يظهر في غير محله | 30m |
| 6 | P1 | Voice input error handling | 30m |
| 7 | P2 | Project Docs قوالب مفيدة | 1h |
| 8 | P2 | Terminal history | 1h |
| 9 | P2 | Upload preview | 1h |
| 10 | P3 | favicon | 5m |
| 11 | P3 | Password form | 5m |
| 12 | P3 | Quick Terminal buttons | 30m |

**المجموع: 12 إصلاح، ~12 ساعة عمل**
