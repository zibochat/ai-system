#!/usr/bin/env python3
"""
اسکریپت بهینه‌سازی سرعت و دقت ZiboChat
"""

import json
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Any
import logging

# Import modules
from recommender import load_data, index_products_to_faiss, recommend
from llm_agent import upsert_user_docs, retrieve_user_memory

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PerformanceOptimizer:
    def __init__(self):
        self.data_dir = Path("data")
        self.faiss_dir = self.data_dir / "faiss"
        self.faiss_dir.mkdir(exist_ok=True)
        
    def preload_data(self):
        """پیش‌بارگذاری داده‌ها"""
        logger.info("🔄 پیش‌بارگذاری داده‌ها...")
        
        start_time = time.time()
        
        # بارگذاری محصولات و نظرات
        products, comments = load_data()
        
        load_time = time.time() - start_time
        logger.info(f"✅ داده‌ها بارگذاری شدند ({load_time:.2f}s)")
        logger.info(f"📊 {len(products)} محصول و {len(comments)} نظر")
        
        return products, comments
    
    def create_product_summaries(self, products: List[Dict], comments: List[Dict]):
        """ایجاد خلاصه‌های محصولات برای سرعت بیشتر"""
        logger.info("🔄 ایجاد خلاصه‌های محصولات...")
        
        summaries = {}
        start_time = time.time()
        
        for product in products:
            product_id = str(product.get("id"))
            name = product.get("full_name") or product.get("nameFa") or product.get("nameEn") or ""
            desc = product.get("description", "")
            
            # پیدا کردن نظرات مرتبط
            related_comments = [c for c in comments if c.get("product_id") == product_id]
            
            # ایجاد خلاصه سریع
            if related_comments:
                comment_texts = [c.get("description", "")[:200] for c in related_comments[:5]]
                summary = f"{name}\n{desc[:300]}\nنظرات: {' '.join(comment_texts)}"
            else:
                summary = f"{name}\n{desc[:500]}"
            
            summaries[product_id] = summary
        
        summary_time = time.time() - start_time
        logger.info(f"✅ خلاصه‌های محصولات ایجاد شدند ({summary_time:.2f}s)")
        
        return summaries
    
    def optimize_faiss_index(self, products: List[Dict], comments: List[Dict]):
        """بهینه‌سازی FAISS index"""
        logger.info("🔄 بهینه‌سازی FAISS index...")
        
        start_time = time.time()
        
        try:
            # ایجاد index محصولات
            count = index_products_to_faiss("products_index")
            
            index_time = time.time() - start_time
            logger.info(f"✅ FAISS index بهینه‌سازی شد ({index_time:.2f}s)")
            logger.info(f"📊 {count} محصول ایندکس شد")
            
            return True
        except Exception as e:
            logger.error(f"❌ خطا در بهینه‌سازی FAISS: {e}")
            return False
    
    def create_user_profiles_cache(self):
        """ایجاد cache پروفایل‌های کاربر"""
        logger.info("🔄 ایجاد cache پروفایل‌های کاربر...")
        
        try:
            from recommender import load_all_profiles
            profiles = load_all_profiles(limit=100)  # محدود کردن برای تست
            
            start_time = time.time()
            
            for i, profile in enumerate(profiles):
                user_id = f"profile_{i}"
                profile_text = json.dumps(profile, ensure_ascii=False)
                
                # ذخیره در FAISS
                doc = {
                    "id": f"profile_{user_id}",
                    "text": profile_text,
                    "meta": {"type": "profile", "user_id": user_id}
                }
                upsert_user_docs(user_id, [doc])
            
            cache_time = time.time() - start_time
            logger.info(f"✅ Cache پروفایل‌ها ایجاد شد ({cache_time:.2f}s)")
            logger.info(f"📊 {len(profiles)} پروفایل cache شد")
            
            return True
        except Exception as e:
            logger.error(f"❌ خطا در ایجاد cache پروفایل‌ها: {e}")
            return False
    
    def test_recommendation_speed(self, products: List[Dict], comments: List[Dict]):
        """تست سرعت توصیه"""
        logger.info("🔄 تست سرعت توصیه...")
        
        test_cases = [
            "سلام",
            "چه محصولی برای پوست خشک پیشنهاد می‌دهید؟",
            "کرم مرطوب کننده می‌خواهم",
            "ضد آفتاب برای پوست حساس",
            "ماسک صورت"
        ]
        
        profile = {"skin_type": "خشک", "age": 25}
        
        times = []
        for test_case in test_cases:
            start_time = time.time()
            try:
                answer, log = recommend(profile, test_case, max_count=3, user_id="test_user")
                end_time = time.time()
                response_time = end_time - start_time
                times.append(response_time)
                logger.info(f"✅ '{test_case[:30]}...' - {response_time:.2f}s")
            except Exception as e:
                logger.error(f"❌ خطا در تست '{test_case}': {e}")
                times.append(float('inf'))
        
        avg_time = sum(times) / len(times) if times else 0
        logger.info(f"📊 میانگین زمان پاسخ: {avg_time:.2f}s")
        
        return avg_time
    
    def optimize_memory_usage(self):
        """بهینه‌سازی استفاده از حافظه"""
        logger.info("🔄 بهینه‌سازی استفاده از حافظه...")
        
        try:
            # پاک کردن cache های قدیمی
            import gc
            gc.collect()
            
            # بررسی حافظه استفاده شده
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            logger.info(f"📊 حافظه استفاده شده: {memory_mb:.2f} MB")
            
            return memory_mb
        except ImportError:
            logger.warning("⚠️ psutil نصب نشده - نمی‌توان حافظه را بررسی کرد")
            return 0
        except Exception as e:
            logger.error(f"❌ خطا در بهینه‌سازی حافظه: {e}")
            return 0
    
    def create_performance_report(self, results: Dict[str, Any]):
        """ایجاد گزارش عملکرد"""
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "optimization_results": results,
            "recommendations": []
        }
        
        # توصیه‌های بهینه‌سازی
        if results.get("avg_response_time", 0) > 5:
            report["recommendations"].append("زمان پاسخ بالا است - استفاده از cache پیشنهاد می‌شود")
        
        if results.get("memory_usage", 0) > 1000:
            report["recommendations"].append("استفاده از حافظه بالا است - بهینه‌سازی داده‌ها پیشنهاد می‌شود")
        
        if not results.get("faiss_optimized", False):
            report["recommendations"].append("FAISS index بهینه‌سازی نشده - پیشنهاد می‌شود")
        
        # ذخیره گزارش
        report_file = Path("performance_report.json")
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📄 گزارش عملکرد در {report_file} ذخیره شد")
        return report
    
    def run_optimization(self):
        """اجرای بهینه‌سازی کامل"""
        logger.info("🚀 شروع بهینه‌سازی ZiboChat...")
        logger.info("=" * 50)
        
        results = {}
        
        # پیش‌بارگذاری داده‌ها
        products, comments = self.preload_data()
        results["data_loaded"] = True
        
        # ایجاد خلاصه‌های محصولات
        summaries = self.create_product_summaries(products, comments)
        results["summaries_created"] = len(summaries)
        
        # بهینه‌سازی FAISS
        faiss_success = self.optimize_faiss_index(products, comments)
        results["faiss_optimized"] = faiss_success
        
        # ایجاد cache پروفایل‌ها
        profile_cache_success = self.create_user_profiles_cache()
        results["profile_cache_created"] = profile_cache_success
        
        # تست سرعت
        avg_time = self.test_recommendation_speed(products, comments)
        results["avg_response_time"] = avg_time
        
        # بهینه‌سازی حافظه
        memory_usage = self.optimize_memory_usage()
        results["memory_usage"] = memory_usage
        
        # ایجاد گزارش
        report = self.create_performance_report(results)
        
        logger.info("\n" + "=" * 50)
        logger.info("🎉 بهینه‌سازی کامل شد!")
        logger.info(f"📊 نتایج: {results}")
        
        return results

def main():
    """تابع اصلی"""
    optimizer = PerformanceOptimizer()
    optimizer.run_optimization()

if __name__ == "__main__":
    main()

