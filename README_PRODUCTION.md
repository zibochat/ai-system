# ZiboChat API - Production Guide

## 🚀 راه‌اندازی سریع

### 1. نصب Dependencies
```bash
pip install -r requirements_production.txt
```

### 2. تنظیم Environment Variables
```bash
cp env.example .env
# فایل .env را ویرایش کنید و API key های خود را وارد کنید
```

### 3. اجرای API
```bash
python run_api.py
```

یا مستقیماً:
```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

## 🐳 Docker Deployment

### با Docker Compose (پیشنهادی)
```bash
# تنظیم environment variables
cp env.example .env
# ویرایش .env

# اجرای با docker-compose
docker-compose up -d
```

### با Docker
```bash
# ساخت image
docker build -t zibochat-api .

# اجرای container
docker run -d \
  --name zibochat-api \
  -p 8000:8000 \
  -e OPENAI_API_KEY=your_key_here \
  -e OPENAI_BASE_URL=your_base_url \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  zibochat-api
```

## 📚 API Endpoints

### Health Check
```bash
GET /health
```

### دریافت پروفایل کاربر
```bash
GET /api/v1/profile/{user_id}
```

### ارسال پیام و دریافت پاسخ
```bash
POST /api/v1/chat
Content-Type: application/json

{
  "user_id": "user123",
  "chat_room_id": "default",
  "message": "سلام، چه محصولی برای پوست خشک پیشنهاد می‌دهید؟"
}
```

### دریافت تاریخچه مکالمه
```bash
GET /api/v1/conversation/{user_id}?chat_room_id=default&limit=50
```

### پاک کردن تاریخچه مکالمه
```bash
DELETE /api/v1/conversation/{user_id}?chat_room_id=default
```

### دریافت حافظه کاربر
```bash
GET /api/v1/memory/{user_id}
```

### ایندکس محصولات (Admin)
```bash
POST /api/v1/admin/index-products
```

## 🔧 تنظیمات Production

### Environment Variables
```bash
# OpenAI
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=openai/gpt-4o-mini

# LangChain
USE_LANGCHAIN=1
RAG_STRICT=1

# Server
HOST=0.0.0.0
PORT=8000
WORKERS=4  # تعداد CPU cores

# Debug
DEBUG_AI=0
```

### Performance Optimization

1. **افزایش Workers**: تعداد workers را برابر با تعداد CPU cores تنظیم کنید
2. **Cache**: از Redis برای cache کردن پروفایل‌ها استفاده کنید
3. **Database**: برای ذخیره‌سازی مکالمات از database استفاده کنید
4. **Load Balancer**: از nginx یا load balancer استفاده کنید

### Security

1. **CORS**: در production محدودیت‌های CORS را تنظیم کنید
2. **Rate Limiting**: محدودیت تعداد درخواست اضافه کنید
3. **Authentication**: سیستم احراز هویت اضافه کنید
4. **HTTPS**: از SSL certificate استفاده کنید

## 📊 Monitoring

### Logs
```bash
# مشاهده logs
tail -f logs/zibochat_api.log
```

### Health Check
```bash
curl http://localhost:8000/health
```

### Stats
```bash
curl http://localhost:8000/api/v1/stats
```

## 🚨 Troubleshooting

### خطای OpenAI Connection
- بررسی API key
- بررسی base URL
- بررسی network connectivity

### خطای FAISS
- بررسی نصب faiss-cpu
- بررسی دسترسی به فایل‌های data

### خطای Memory
- بررسی دسترسی به پوشه logs
- بررسی disk space

## 📈 Scaling

### Horizontal Scaling
- استفاده از load balancer
- اجرای چندین instance
- استفاده از container orchestration (Kubernetes)

### Vertical Scaling
- افزایش RAM
- افزایش CPU cores
- استفاده از SSD

## 🔄 Backup & Recovery

### Backup
```bash
# Backup data
tar -czf backup_$(date +%Y%m%d).tar.gz data/ logs/
```

### Recovery
```bash
# Restore data
tar -xzf backup_20231201.tar.gz
```

## 📞 Support

برای پشتیبانی و گزارش مشکل، لطفاً با تیم توسعه تماس بگیرید.
