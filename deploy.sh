#!/bin/bash

# ZiboChat Production Deployment Script
# اسکریپت deployment برای production

set -e  # Exit on any error

echo "🚀 شروع deployment ZiboChat API..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 نصب نشده است"
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    print_error "pip3 نصب نشده است"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    print_status "ایجاد virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
print_status "فعال‌سازی virtual environment..."
source venv/bin/activate

# Install requirements
print_status "نصب requirements..."
pip install -r requirements_production.txt

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_warning "فایل .env یافت نشد"
    if [ -f "env.example" ]; then
        print_status "کپی کردن env.example به .env..."
        cp env.example .env
        print_warning "لطفاً فایل .env را ویرایش کنید و API key های خود را وارد کنید"
    else
        print_error "فایل env.example یافت نشد"
        exit 1
    fi
fi

# Check if data files exist
if [ ! -f "data/products.json" ]; then
    print_error "فایل data/products.json یافت نشد"
    exit 1
fi

if [ ! -f "data/comments.json" ]; then
    print_error "فایل data/comments.json یافت نشد"
    exit 1
fi

if [ ! -f "data/shenakht_poosti.xlsx" ]; then
    print_error "فایل data/shenakht_poosti.xlsx یافت نشد"
    exit 1
fi

# Create necessary directories
print_status "ایجاد پوشه‌های لازم..."
mkdir -p logs
mkdir -p data/faiss

# Run optimization
print_status "اجرای بهینه‌سازی..."
python optimize_performance.py

# Test API
print_status "تست API..."
python test_api.py --message "full"

# Start API
print_status "راه‌اندازی API..."
echo "🌐 API روی http://localhost:8000 در دسترس است"
echo "📚 Documentation: http://localhost:8000/docs"
echo "🔍 Health Check: http://localhost:8000/health"
echo ""
echo "برای متوقف کردن API، Ctrl+C را فشار دهید"
echo ""

# Run API
python run_api.py

