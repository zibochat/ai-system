# ZiboChat Production - خلاصه کارها

## ✅ کارهای انجام شده

### 1. تغییر nameFa/nameEn به full_name
- تمام فایل‌ها به‌روزرسانی شدند تا از `full_name` استفاده کنند
- پشتیبانی از فیلدهای قدیمی برای سازگاری

### 2. FastAPI Endpoints برای Production
- **`api.py`**: API کامل با تمام endpoints
- **Health Check**: `/health` برای monitoring
- **User Profile**: `/api/v1/profile/{user_id}` برای دریافت/به‌روزرسانی پروفایل
- **Chat**: `/api/v1/chat` برای ارسال پیام و دریافت پاسخ
- **Conversation**: `/api/v1/conversation/{user_id}` برای تاریخچه مکالمه
- **Memory**: `/api/v1/memory/{user_id}` برای حافظه کاربر
- **Admin**: `/api/v1/admin/index-products` برای ایندکس محصولات

### 3. مدیریت حافظه چت
- **Chat Rooms**: پشتیبانی از chat rooms مختلف
- **Memory Management**: حافظه برای هر user_id
- **Conversation History**: ذخیره و بازیابی مکالمات
- **Background Tasks**: ذخیره تعاملات در پس‌زمینه

### 4. بهینه‌سازی سرعت و دقت
- **FAISS Index**: ایندکس محصولات برای جستجوی سریع
- **Caching**: cache پروفایل‌ها و داده‌ها
- **Performance Monitoring**: نظارت بر عملکرد
- **Memory Optimization**: بهینه‌سازی استفاده از حافظه

### 5. فایل‌های Production
- **`requirements_production.txt`**: dependencies برای production
- **`Dockerfile`**: containerization
- **`docker-compose.yml`**: orchestration
- **`env.example`**: نمونه environment variables
- **`run_api.py`**: اسکریپت اجرای API
- **`test_api.py`**: تست API
- **`optimize_performance.py`**: بهینه‌سازی عملکرد
- **`deploy.sh`**: اسکریپت deployment

## 🚀 راه‌اندازی سریع

### روش 1: اسکریپت خودکار
```bash
./deploy.sh
```

### روش 2: دستی
```bash
# نصب dependencies
pip install -r requirements_production.txt

# تنظیم environment
cp env.example .env
# ویرایش .env

# اجرای API
python run_api.py
```

### روش 3: Docker
```bash
# تنظیم environment
cp env.example .env
# ویرایش .env

# اجرای با docker-compose
docker-compose up -d
```

## 📚 API Endpoints

### دریافت پروفایل کاربر
```bash
GET /api/v1/profile/{user_id}
```

### ارسال پیام و دریافت پاسخ
```bash
POST /api/v1/chat
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

## 🔧 تنظیمات مهم

### Environment Variables
```bash
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=openai/gpt-4o-mini
USE_LANGCHAIN=1
RAG_STRICT=1
HOST=0.0.0.0
PORT=8000
WORKERS=4
```

### Performance Settings
- **Workers**: تعداد CPU cores
- **RAG_STRICT**: استفاده سخت‌گیرانه از FAISS
- **USE_LANGCHAIN**: فعال‌سازی LangChain

## 📊 Monitoring

### Health Check
```bash
curl http://localhost:8000/health
```

### Stats
```bash
curl http://localhost:8000/api/v1/stats
```

### Logs
```bash
tail -f logs/zibochat_api.log
```

## 🧪 Testing

### تست کامل
```bash
python test_api.py --message full
```

### تست ساده
```bash
python test_api.py --user test_user --message "سلام"
```

## 🚨 نکات مهم

### 1. Security
- در production محدودیت‌های CORS را تنظیم کنید
- از HTTPS استفاده کنید
- سیستم احراز هویت اضافه کنید

### 2. Performance
- تعداد workers را برابر CPU cores تنظیم کنید
- از Redis برای cache استفاده کنید
- از load balancer استفاده کنید

### 3. Monitoring
- logs را نظارت کنید
- health check را تنظیم کنید
- metrics را جمع‌آوری کنید

## 📈 Scaling

### Horizontal Scaling
- اجرای چندین instance
- استفاده از load balancer
- container orchestration

### Vertical Scaling
- افزایش RAM
- افزایش CPU cores
- استفاده از SSD

## 🔄 Backup & Recovery

### Backup
```bash
tar -czf backup_$(date +%Y%m%d).tar.gz data/ logs/
```

### Recovery
```bash
tar -xzf backup_20231201.tar.gz
```

## 📞 Support

برای پشتیبانی و گزارش مشکل، لطفاً با تیم توسعه تماس بگیرید.

---

## 🎉 خلاصه

ZiboChat API حالا آماده production است با:
- ✅ FastAPI endpoints کامل
- ✅ مدیریت حافظه چت
- ✅ پشتیبانی از chat rooms
- ✅ بهینه‌سازی سرعت و دقت
- ✅ Docker support
- ✅ Monitoring و testing
- ✅ Documentation کامل

**آماده برای deployment! 🚀**

