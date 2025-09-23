#!/usr/bin/env python3
"""
اسکریپت تست ZiboChat API
"""

import requests
import json
import time
from typing import Dict, Any

class ZiboChatAPITester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def test_health(self) -> bool:
        """تست health check"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            if response.status_code == 200:
                print("✅ Health check passed")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False
    
    def test_get_profile(self, user_id: str = "test_user") -> Dict[str, Any]:
        """تست دریافت پروفایل"""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/profile/{user_id}")
            if response.status_code == 200:
                profile = response.json()
                print(f"✅ Profile retrieved for user {user_id}")
                return profile
            else:
                print(f"❌ Profile retrieval failed: {response.status_code}")
                return {}
        except Exception as e:
            print(f"❌ Profile retrieval error: {e}")
            return {}
    
    def test_chat(self, user_id: str = "test_user", message: str = "سلام") -> Dict[str, Any]:
        """تست چت"""
        try:
            payload = {
                "user_id": user_id,
                "chat_room_id": "default",
                "message": message
            }
            response = self.session.post(
                f"{self.base_url}/api/v1/chat",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 200:
                chat_response = response.json()
                print(f"✅ Chat successful: {chat_response['response'][:100]}...")
                return chat_response
            else:
                print(f"❌ Chat failed: {response.status_code}")
                return {}
        except Exception as e:
            print(f"❌ Chat error: {e}")
            return {}
    
    def test_conversation_history(self, user_id: str = "test_user") -> Dict[str, Any]:
        """تست دریافت تاریخچه مکالمه"""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/conversation/{user_id}")
            if response.status_code == 200:
                history = response.json()
                print(f"✅ Conversation history retrieved: {history['total_count']} messages")
                return history
            else:
                print(f"❌ Conversation history failed: {response.status_code}")
                return {}
        except Exception as e:
            print(f"❌ Conversation history error: {e}")
            return {}
    
    def test_memory(self, user_id: str = "test_user") -> Dict[str, Any]:
        """تست دریافت حافظه"""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/memory/{user_id}")
            if response.status_code == 200:
                memory = response.json()
                print(f"✅ Memory retrieved for user {user_id}")
                return memory
            else:
                print(f"❌ Memory retrieval failed: {response.status_code}")
                return {}
        except Exception as e:
            print(f"❌ Memory retrieval error: {e}")
            return {}
    
    def test_stats(self) -> Dict[str, Any]:
        """تست دریافت آمار"""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/stats")
            if response.status_code == 200:
                stats = response.json()
                print(f"✅ Stats retrieved: {stats}")
                return stats
            else:
                print(f"❌ Stats retrieval failed: {response.status_code}")
                return {}
        except Exception as e:
            print(f"❌ Stats retrieval error: {e}")
            return {}
    
    def run_full_test(self):
        """اجرای تست کامل"""
        print("🧪 شروع تست ZiboChat API...")
        print("=" * 50)
        
        # تست health
        if not self.test_health():
            print("❌ API در دسترس نیست. لطفاً ابتدا API را راه‌اندازی کنید.")
            return
        
        # تست دریافت پروفایل
        profile = self.test_get_profile("test_user")
        
        # تست چت
        chat_response = self.test_chat("test_user", "سلام، چه محصولی برای پوست خشک پیشنهاد می‌دهید؟")
        
        # تست چت دوم
        chat_response2 = self.test_chat("test_user", "ممنون، آیا محصول دیگری هم دارید؟")
        
        # تست دریافت تاریخچه
        history = self.test_conversation_history("test_user")
        
        # تست دریافت حافظه
        memory = self.test_memory("test_user")
        
        # تست آمار
        stats = self.test_stats()
        
        print("\n" + "=" * 50)
        print("🎉 تست کامل انجام شد!")
        
        # خلاصه نتایج
        print("\n📊 خلاصه نتایج:")
        print(f"- پروفایل: {'✅' if profile else '❌'}")
        print(f"- چت اول: {'✅' if chat_response else '❌'}")
        print(f"- چت دوم: {'✅' if chat_response2 else '❌'}")
        print(f"- تاریخچه: {'✅' if history else '❌'}")
        print(f"- حافظه: {'✅' if memory else '❌'}")
        print(f"- آمار: {'✅' if stats else '❌'}")

def main():
    """تابع اصلی"""
    import argparse
    
    parser = argparse.ArgumentParser(description="ZiboChat API Tester")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--user", default="test_user", help="Test user ID")
    parser.add_argument("--message", default="سلام", help="Test message")
    
    args = parser.parse_args()
    
    tester = ZiboChatAPITester(args.url)
    
    if args.message == "full":
        tester.run_full_test()
    else:
        # تست ساده
        print(f"🧪 تست ساده API: {args.url}")
        print("=" * 30)
        
        if tester.test_health():
            tester.test_get_profile(args.user)
            tester.test_chat(args.user, args.message)
            tester.test_conversation_history(args.user)
            tester.test_stats()

if __name__ == "__main__":
    main()

