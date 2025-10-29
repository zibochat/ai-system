# ZiboChat API - Curl Tests

این مجموعه شامل تست‌های جامع curl برای تمام endpoint های ZiboChat API است.

## فایل‌های موجود

- `curl_tests.sh` - اسکریپت bash برای اجرای تمام تست‌ها
- `curl_tests.json` - فایل JSON شامل تمام تست‌ها و نمونه دستورات
- `README_CURL_TESTS.md` - این فایل راهنما

## پیش‌نیازها

1. **راه‌اندازی سرور API:**
   ```bash
   python run_api.py
   ```
   یا
   ```bash
   uvicorn api:app --host 0.0.0.0 --port 8000
   ```

2. **بررسی اتصال:**
   ```bash
   curl http://localhost:8000/health
   ```

## اجرای تست‌ها

### اجرای تمام تست‌ها
```bash
chmod +x curl_tests.sh
./curl_tests.sh
```

### اجرای تست‌های جداگانه

#### Health Check
```bash
curl http://localhost:8000/
curl http://localhost:8000/health
```

#### User Profile
```bash
# دریافت پروفایل
curl http://localhost:8000/api/v1/profile/user_123

# به‌روزرسانی پروفایل
curl -X POST http://localhost:8000/api/v1/profile/user_123 \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "user_123",
    "skin_type": "oily",
    "age": 25,
    "skin_concerns": ["acne", "dark_spots"]
  }'
```

#### Chat
```bash
# ارسال پیام
curl -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "user_123",
    "chat_id": "chat_456",
    "message": "سلام، من پوست چرب دارم و دنبال کرم ضد آفتاب هستم"
  }'
```

#### Conversation History
```bash
# دریافت تاریخچه مکالمه
curl http://localhost:8000/api/v1/conversation/user_123?chat_id=chat_456&limit=10

# پاک کردن تاریخچه
curl -X DELETE http://localhost:8000/api/v1/conversation/user_123?chat_id=chat_456
```

#### Memory
```bash
curl http://localhost:8000/api/v1/memory/user_123
```

#### Admin
```bash
curl -X POST http://localhost:8000/api/v1/admin/index-products
```

#### Stats
```bash
curl http://localhost:8000/api/v1/stats
```

## Endpoint های موجود

### Health Check
- `GET /` - بررسی سلامت پایه
- `GET /health` - بررسی سلامت تفصیلی

### User Profile
- `GET /api/v1/profile/{user_id}` - دریافت پروفایل کاربر
- `POST /api/v1/profile/{user_id}` - به‌روزرسانی پروفایل کاربر

### Chat
- `POST /api/v1/chat` - ارسال پیام و دریافت پاسخ

### Conversation History
- `GET /api/v1/conversation/{user_id}` - دریافت تاریخچه مکالمه
- `DELETE /api/v1/conversation/{user_id}` - پاک کردن تاریخچه مکالمه

### Memory
- `GET /api/v1/memory/{user_id}` - دریافت خلاصه حافظه کاربر

### Admin
- `POST /api/v1/admin/index-products` - ایندکس کردن محصولات

### Stats
- `GET /api/v1/stats` - آمار سیستم

### Documentation
- `GET /docs` - مستندات Swagger UI
- `GET /openapi.json` - Schema OpenAPI

## تست‌های خاص

### تست‌های Error Handling
- Endpoint نامعتبر (404)
- پیام خالی (400)
- JSON نامعتبر (422)

### تست‌های Edge Cases
- کاراکترهای خاص در user_id
- کاراکترهای Unicode در پیام
- User ID بسیار طولانی
- پارامتر limit بزرگ

### تست‌های پیشرفته
- چندین پیام در یک chat
- کاربران مختلف با chat های مختلف
- پیام‌های طولانی و تفصیلی

## سفارشی‌سازی

### تغییر URL پایه
در فایل `curl_tests.sh` متغیر `BASE_URL` را تغییر دهید:
```bash
BASE_URL="http://your-server:port"
```

### اضافه کردن تست جدید
در فایل `curl_tests.json` بخش `tests` را ویرایش کنید.

### تغییر داده‌های تست
در بخش `body` هر تست، داده‌های JSON را تغییر دهید.

## نکات مهم

1. **سرور باید در حال اجرا باشد** قبل از اجرای تست‌ها
2. **برخی تست‌ها ممکن است خطا دهند** اگر داده واقعی وجود نداشته باشد
3. **تست‌های chat** نیاز به اتصال OpenAI دارند
4. **تست‌های admin** ممکن است زمان‌بر باشند

## عیب‌یابی

### خطای Connection Refused
```bash
curl: (7) Failed to connect to localhost port 8000: Connection refused
```
**راه‌حل:** سرور API را راه‌اندازی کنید

### خطای 500 Internal Server Error
**راه‌حل:** لاگ‌های سرور را بررسی کنید:
```bash
tail -f logs/zibochat_api.log
```

### خطای OpenAI API
**راه‌حل:** کلید API OpenAI را بررسی کنید:
```bash
echo $OPENAI_API_KEY
```

## مثال‌های کاربردی

### تست کامل یک کاربر
```bash
# 1. دریافت پروفایل
curl http://localhost:8000/api/v1/profile/user_test

# 2. ارسال پیام
curl -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "user_test", "message": "سلام"}'

# 3. دریافت تاریخچه
curl http://localhost:8000/api/v1/conversation/user_test

# 4. دریافت حافظه
curl http://localhost:8000/api/v1/memory/user_test
```

### تست عملکرد
```bash
# تست زمان پاسخ
time curl http://localhost:8000/health

# تست همزمان
for i in {1..5}; do
  curl http://localhost:8000/api/v1/stats &
done
wait
```

## پشتیبانی

برای گزارش مشکل یا درخواست تست جدید، لطفاً issue ایجاد کنید یا با تیم توسعه تماس بگیرید.
