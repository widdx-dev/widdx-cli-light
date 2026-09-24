# WIDDX Nexus — دليل النشر الكامل (Deployment Guide)

> **الإصدار**: 3.3.0  
> **آخر تحديث**: 2026-07-23  
> **المؤلف**: MUHAMMAD MUSLIH (muhammed@widdx.com)

---

## 📋 المتطلبات الأساسية

| المكون | الإصدار الأدنى | ملاحظات |
|--------|---------------|---------|
| Python | 3.10+ | 3.11+ موصى به |
| Docker | 24.0+ | للنشر عبر الحاويات |
| Docker Compose | 2.20+ | V2 format |
| Nginx | 1.24+ | عكس الوكيل + SSL |
| Certbot | 2.0+ | شهادات SSL مجانية |
| Prometheus (اختياري) | 2.50+ | للمراقبة |
| Grafana (اختياري) | 10.0+ | للوحات القيادة |

---

## 🚀 النشر السريع (Docker)

### 1. التحضير

```bash
# استنساخ المشروع
git clone https://github.com/widdx1990/widdx-cli-light.git
cd widdx-cli-light

# إعداد المتغيرات البيئية
cp .env.example .env
# قم بتعديل .env — غير WIDDX_API_KEY إلى مفتاح قوي!
```

### 2. تشغيل الخدمات

```bash
# بناء وتشغيل جميع الخدمات
docker compose up -d

# متابعة السجلات
docker compose logs -f

# التحقق من الصحة
curl http://localhost:8000/api/health \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### 3. مراقبة الأداء (اختياري)

```bash
# تشغيل Prometheus + Grafana
docker compose -f deploy/docker-compose.monitoring.yml up -d

# Grafana: http://localhost:3000 (admin/admin)
# Prometheus: http://localhost:9090
```

---

## 🔧 النشر اليدوي (بدون Docker)

### 1. تثبيت المتغيرات

```bash
python -m venv venv
source venv/bin/activate
pip install -e ".[api,dev]"
```

### 2. تشغيل الخادم

```bash
# API Server
WIDDX_API_KEY="your-secret-key" widdx-api --port 8001

# Web UI (في نافذة أخرى)
WIDDX_API_KEY="your-secret-key" widdx-web --port 8000
```

---

## 🌐 إعداد Nginx + SSL

### 1. تثبيت Nginx

```bash
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx
```

### 2. تكوين Nginx

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/widdx
sudo sed -i 's/widdx.yourdomain.com/YOUR_DOMAIN/g' /etc/nginx/sites-available/widdx
sudo ln -s /etc/nginx/sites-available/widdx /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 3. إعداد SSL

```bash
# قم بتعيين المجال والبريد الإلكتروني
export WIDDX_DOMAIN="yourdomain.com"
export WIDDX_EMAIL="admin@yourdomain.com"

# تثبيت SSL تلقائيًا
bash deploy/ssl-setup.sh install
bash deploy/ssl-setup.sh auto-renew
```

---

## 💾 النسخ الاحتياطي

### 1. تشغيل يدوي

```bash
# نسخ احتياطي
bash deploy/backup.sh backup

# سرد النسخ
bash deploy/backup.sh list

# استعادة
bash deploy/backup.sh restore backups/widdx_backup_20260723_120000.tar.gz
```

### 2. جدولة تلقائية

```bash
# نسخ احتياطي يومي في الساعة 2 صباحًا
bash deploy/backup.sh cron
```

---

## 📊 المراقبة (Prometheus + Grafana)

### 1. تشغيل مكدس المراقبة

```bash
docker compose -f deploy/docker-compose.monitoring.yml up -d
```

### 2. إعداد Grafana

1. افتح http://localhost:3000 (admin/admin)
2. أضف مصدر بيانات → Prometheus → `http://prometheus:9090`
3. استورد لوحة التحكم من `deploy/grafana-dashboard.json`

---

## ✅ التحقق من النشر

### 1. اختبارات الصحة

```bash
# Liveness probe
curl http://localhost:8001/api/livez

# Readiness probe  
curl http://localhost:8001/api/ready

# Health (with auth)
curl -H "Authorization: Bearer YOUR_KEY" http://localhost:8001/api/health
```

### 2. مقاييس Prometheus

```bash
curl http://localhost:8001/metrics
```

### 3. اختبار الإجهاد

```bash
# اختبار سريع
bash scripts/run_stress_tests.sh quick

# اختبار شامل
WIDDX_API_KEY="your-key" bash scripts/run_stress_tests.sh full
```

---

## 🔐 الأمان

### المتغيرات البيئية المطلوبة

| المتغير | إلزامي | الوصف |
|---------|--------|-------|
| `WIDDX_API_KEY` | ✅ | مفتاح API للخادم |
| `WIDDX_LLM_API_KEY` | ✅ | مفتاح API لمزود LLM |
| `WIDDX_CORS_ORIGINS` | ✅ | النطاقات المسموح بها |

### تحقق من القائمة

- [ ] `WIDDX_API_KEY` ليس القيمة الافتراضية
- [ ] `WIDDX_CORS_ORIGINS` محدد بدقة (ليس `*`)
- [ ] SSL/TLS مفعل عبر Let's Encrypt
- [ ] قاعدة البيانات في `.widdx/` محمية
- [ ] Nginx rate limiting مفعل
- [ ] النسخ الاحتياطي مجدول

---

## 🆘 استكشاف الأخطاء

| المشكلة | الحل |
|---------|------|
| `401 Unauthorized` | تأكد من تعيين `WIDDX_API_KEY` بشكل صحيح |
| `429 Too Many Requests` | زادت الطلبات — انتظر أو زد `WIDDX_RATE_LIMIT_MAX` |
| `413 Request too large` | زد `WIDDX_MAX_BODY_BYTES` |
| CORS error | تحقق من `WIDDX_CORS_ORIGINS` |
| قاعدة البيانات مؤمنة | احذف `.widdx/widdx.db` وابدأ من جديد |
| الذاكرة مرتفعة | قلل `WIDDX_MAX_MEMORIES` أو أعد تشغيل الخادم |
