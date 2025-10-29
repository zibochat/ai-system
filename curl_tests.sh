#!/bin/bash

# ZiboChat API - Curl Tests
# این فایل شامل تست‌های curl برای تمام endpoint های API است
# برای اجرا: chmod +x curl_tests.sh && ./curl_tests.sh

# تنظیمات پایه
BASE_URL="http://localhost:8000"
API_BASE="${BASE_URL}/api/v1"

# رنگ‌ها برای خروجی بهتر
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}    ZiboChat API - Curl Tests${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# تابع برای نمایش نتیجه تست
show_result() {
    local test_name="$1"
    local status_code="$2"
    local response="$3"
    
    if [ "$status_code" -eq 200 ] || [ "$status_code" -eq 201 ]; then
        echo -e "${GREEN}✅ $test_name - Status: $status_code${NC}"
    else
        echo -e "${RED}❌ $test_name - Status: $status_code${NC}"
    fi
    
    if [ ! -z "$response" ]; then
        echo -e "${YELLOW}Response: $response${NC}"
    fi
    echo ""
}

# تابع برای اجرای تست
run_test() {
    local test_name="$1"
    local curl_command="$2"
    
    echo -e "${BLUE}Testing: $test_name${NC}"
    
    # اجرای curl و ذخیره خروجی
    local result=$(eval "$curl_command" 2>/dev/null)
    local status_code=$(echo "$result" | tail -n1)
    local response=$(echo "$result" | head -n -1)
    
    show_result "$test_name" "$status_code" "$response"
}

echo -e "${YELLOW}شروع تست‌های API...${NC}"
echo ""

# ========================================
# 1. Health Check Endpoints
# ========================================

echo -e "${BLUE}--- Health Check Endpoints ---${NC}"

# Root endpoint
run_test "Root Health Check" "curl -s -w '%{http_code}' -o /dev/null '$BASE_URL/'"

# Detailed health check
run_test "Detailed Health Check" "curl -s -w '%{http_code}' -o /dev/null '$BASE_URL/health'"

# ========================================
# 2. User Profile Endpoints
# ========================================

echo -e "${BLUE}--- User Profile Endpoints ---${NC}"

# Get user profile
run_test "Get User Profile (user_123)" "curl -s -w '%{http_code}' -o /dev/null '$API_BASE/profile/user_123'"

# Get user profile with numeric ID
run_test "Get User Profile (numeric ID)" "curl -s -w '%{http_code}' -o /dev/null '$API_BASE/profile/1'"

# Update user profile
run_test "Update User Profile" "curl -s -w '%{http_code}' -X POST '$API_BASE/profile/user_123' \
    -H 'Content-Type: application/json' \
    -d '{
        \"user_id\": \"user_123\",
        \"skin_type\": \"oily\",
        \"age\": 25,
        \"skin_concerns\": [\"acne\", \"dark_spots\"],
        \"preferences\": {\"brand\": \"loreal\", \"price_range\": \"medium\"}
    }'"

# ========================================
# 3. Chat Endpoints
# ========================================

echo -e "${BLUE}--- Chat Endpoints ---${NC}"

# Send chat message
run_test "Send Chat Message" "curl -s -w '%{http_code}' -X POST '$API_BASE/chat' \
    -H 'Content-Type: application/json' \
    -d '{
        \"user_id\": \"user_123\",
        \"chat_id\": \"chat_456\",
        \"message\": \"سلام، من پوست چرب دارم و دنبال کرم ضد آفتاب هستم\"
    }'"

# Send chat message with chat_room_id (backward compatibility)
run_test "Send Chat Message (with chat_room_id)" "curl -s -w '%{http_code}' -X POST '$API_BASE/chat' \
    -H 'Content-Type: application/json' \
    -d '{
        \"user_id\": \"user_123\",
        \"chat_room_id\": \"room_789\",
        \"message\": \"کدام محصولات برای پوست حساس مناسب هستند؟\"
    }'"

# Send chat message without chat_id (uses default)
run_test "Send Chat Message (default chat)" "curl -s -w '%{http_code}' -X POST '$API_BASE/chat' \
    -H 'Content-Type: application/json' \
    -d '{
        \"user_id\": \"user_123\",
        \"message\": \"لطفاً محصولات ضد پیری معرفی کنید\"
    }'"

# ========================================
# 4. Conversation History Endpoints
# ========================================

echo -e "${BLUE}--- Conversation History Endpoints ---${NC}"

# Get conversation history
run_test "Get Conversation History" "curl -s -w '%{http_code}' -o /dev/null '$API_BASE/conversation/user_123?chat_id=chat_456&limit=10'"

# Get conversation history with chat_room_id
run_test "Get Conversation History (with chat_room_id)" "curl -s -w '%{http_code}' -o /dev/null '$API_BASE/conversation/user_123?chat_room_id=room_789&limit=5'"

# Get conversation history without chat_id (uses default)
run_test "Get Conversation History (default)" "curl -s -w '%{http_code}' -o /dev/null '$API_BASE/conversation/user_123?limit=20'"

# Clear conversation history
run_test "Clear Conversation History" "curl -s -w '%{http_code}' -X DELETE '$API_BASE/conversation/user_123?chat_id=chat_456'"

# Clear conversation history with chat_room_id
run_test "Clear Conversation History (with chat_room_id)" "curl -s -w '%{http_code}' -X DELETE '$API_BASE/conversation/user_123?chat_room_id=room_789'"

# ========================================
# 5. Memory Endpoints
# ========================================

echo -e "${BLUE}--- Memory Endpoints ---${NC}"

# Get user memory summary
run_test "Get User Memory Summary" "curl -s -w '%{http_code}' -o /dev/null '$API_BASE/memory/user_123'"

# ========================================
# 6. Admin Endpoints
# ========================================

echo -e "${BLUE}--- Admin Endpoints ---${NC}"

# Index products
run_test "Index Products (Admin)" "curl -s -w '%{http_code}' -X POST '$API_BASE/admin/index-products'"

# ========================================
# 7. Stats Endpoints
# ========================================

echo -e "${BLUE}--- Stats Endpoints ---${NC}"

# Get system stats
run_test "Get System Stats" "curl -s -w '%{http_code}' -o /dev/null '$API_BASE/stats'"

# ========================================
# 8. Error Handling Tests
# ========================================

echo -e "${BLUE}--- Error Handling Tests ---${NC}"

# Test invalid endpoint
run_test "Invalid Endpoint (404)" "curl -s -w '%{http_code}' -o /dev/null '$API_BASE/invalid-endpoint'"

# Test empty message
run_test "Empty Message (400)" "curl -s -w '%{http_code}' -X POST '$API_BASE/chat' \
    -H 'Content-Type: application/json' \
    -d '{
        \"user_id\": \"user_123\",
        \"message\": \"\"
    }'"

# Test invalid JSON
run_test "Invalid JSON (422)" "curl -s -w '%{http_code}' -X POST '$API_BASE/chat' \
    -H 'Content-Type: application/json' \
    -d '{\"user_id\": \"user_123\", \"message\": \"test\"'"

# ========================================
# 9. Advanced Chat Scenarios
# ========================================

echo -e "${BLUE}--- Advanced Chat Scenarios ---${NC}"

# Multiple messages in same chat
run_test "Multiple Messages Same Chat" "curl -s -w '%{http_code}' -X POST '$API_BASE/chat' \
    -H 'Content-Type: application/json' \
    -d '{
        \"user_id\": \"user_123\",
        \"chat_id\": \"chat_advanced\",
        \"message\": \"من پوست خشک دارم\"
    }'"

# Different user, different chat
run_test "Different User Different Chat" "curl -s -w '%{http_code}' -X POST '$API_BASE/chat' \
    -H 'Content-Type: application/json' \
    -d '{
        \"user_id\": \"user_456\",
        \"chat_id\": \"chat_different\",
        \"message\": \"کدام شامپو برای موهای چرب مناسب است؟\"
    }'"

# Long message
run_test "Long Message" "curl -s -w '%{http_code}' -X POST '$API_BASE/chat' \
    -H 'Content-Type: application/json' \
    -d '{
        \"user_id\": \"user_123\",
        \"message\": \"سلام، من یک خانم ۳۰ ساله هستم و پوست ترکیبی دارم. در ناحیه T-zone چرب و در بقیه جاها خشک است. اخیراً متوجه شدم که لکه‌های تیره روی پیشانی‌ام ایجاد شده و همچنین چند جوش کوچک روی چانه‌ام دارم. می‌خواهم یک روتین کامل مراقبت از پوست برای صبح و شب داشته باشم. بودجه من متوسط است و ترجیح می‌دهم از برندهای ایرانی استفاده کنم. لطفاً محصولات مناسب را معرفی کنید.\"
    }'"

# ========================================
# 10. Performance Tests
# ========================================

echo -e "${BLUE}--- Performance Tests ---${NC}"

# Test with large limit
run_test "Large Limit Parameter" "curl -s -w '%{http_code}' -o /dev/null '$API_BASE/conversation/user_123?limit=1000'"

# Test concurrent requests simulation (simple)
run_test "Concurrent Request Simulation" "curl -s -w '%{http_code}' -o /dev/null '$API_BASE/profile/user_123'"

# ========================================
# 11. Edge Cases
# ========================================

echo -e "${BLUE}--- Edge Cases ---${NC}"

# Special characters in user_id
run_test "Special Characters in User ID" "curl -s -w '%{http_code}' -o /dev/null '$API_BASE/profile/user-123_test'"

# Unicode characters in message
run_test "Unicode Characters in Message" "curl -s -w '%{http_code}' -X POST '$API_BASE/chat' \
    -H 'Content-Type: application/json' \
    -d '{
        \"user_id\": \"user_123\",
        \"message\": \"سلام! من دنبال محصولات مراقبت از پوست هستم. 🧴✨\"
    }'"

# Very long user_id
run_test "Very Long User ID" "curl -s -w '%{http_code}' -o /dev/null '$API_BASE/profile/$(printf \"a%.0s\" {1..100})'"

# ========================================
# 12. API Documentation Tests
# ========================================

echo -e "${BLUE}--- API Documentation Tests ---${NC}"

# OpenAPI docs
run_test "OpenAPI Documentation" "curl -s -w '%{http_code}' -o /dev/null '$BASE_URL/docs'"

# OpenAPI JSON schema
run_test "OpenAPI JSON Schema" "curl -s -w '%{http_code}' -o /dev/null '$BASE_URL/openapi.json'"

# ========================================
# خلاصه نتایج
# ========================================

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}    تست‌های API تکمیل شد${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}نکات مهم:${NC}"
echo "• تمام تست‌ها با فرض اجرای سرور روی localhost:8000 نوشته شده‌اند"
echo "• برای تغییر URL، متغیر BASE_URL را تغییر دهید"
echo "• برخی تست‌ها ممکن است به دلیل عدم وجود داده واقعی خطا دهند"
echo "• برای تست‌های کامل، ابتدا سرور را راه‌اندازی کنید:"
echo "  python run_api.py"
echo ""
echo -e "${GREEN}برای اجرای تست‌ها:${NC}"
echo "chmod +x curl_tests.sh"
echo "./curl_tests.sh"
echo ""
echo -e "${BLUE}تست‌های جداگانه:${NC}"
echo "# تست health check"
echo "curl $BASE_URL/health"
echo ""
echo "# تست chat"
echo "curl -X POST '$API_BASE/chat' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"user_id\": \"test\", \"message\": \"سلام\"}'"
echo ""
echo "# تست profile"
echo "curl '$API_BASE/profile/test_user'"
