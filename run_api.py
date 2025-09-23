#!/usr/bin/env python3
"""
اسکریپت اجرای ZiboChat API
"""

import os
import sys
import subprocess
from pathlib import Path

def check_requirements():
    """بررسی نصب requirements"""
    try:
        import fastapi
        import uvicorn
        import openai
        print("✅ تمام requirements نصب شده‌اند")
        return True
    except ImportError as e:
        print(f"❌ Requirements نصب نشده: {e}")
        print("لطفاً ابتدا requirements را نصب کنید:")
        print("pip install -r requirements_production.txt")
        return False

def check_env_file():
    """بررسی وجود فایل .env"""
    env_file = Path(".env")
    if not env_file.exists():
        print("⚠️  فایل .env یافت نشد")
        print("لطفاً فایل .env را از env.example کپی کنید و تنظیمات را انجام دهید")
        return False
    return True

def check_data_files():
    """بررسی وجود فایل‌های داده"""
    data_dir = Path("data")
    required_files = ["products.json", "comments.json", "shenakht_poosti.xlsx"]
    
    missing_files = []
    for file in required_files:
        if not (data_dir / file).exists():
            missing_files.append(file)
    
    if missing_files:
        print(f"⚠️  فایل‌های داده یافت نشد: {missing_files}")
        return False
    
    print("✅ فایل‌های داده موجود هستند")
    return True

def main():
    """تابع اصلی"""
    print("🚀 راه‌اندازی ZiboChat API...")
    
    # بررسی‌های اولیه
    if not check_requirements():
        sys.exit(1)
    
    if not check_env_file():
        sys.exit(1)
    
    if not check_data_files():
        sys.exit(1)
    
    # تنظیمات سرور
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    workers = int(os.getenv("WORKERS", 1))
    
    print(f"🌐 سرور روی {host}:{port} راه‌اندازی می‌شود")
    print(f"👥 تعداد workers: {workers}")
    print("📚 API Documentation: http://localhost:8000/docs")
    print("🔍 Health Check: http://localhost:8000/health")
    print("\n" + "="*50)
    
    # اجرای سرور
    try:
        subprocess.run([
            "uvicorn", "api:app",
            "--host", host,
            "--port", str(port),
            "--workers", str(workers),
            "--reload" if os.getenv("DEBUG", "0") == "1" else "--no-reload"
        ])
    except KeyboardInterrupt:
        print("\n👋 سرور متوقف شد")
    except Exception as e:
        print(f"❌ خطا در اجرای سرور: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

