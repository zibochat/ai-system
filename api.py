#!/usr/bin/env python3
"""
FastAPI endpoints برای ZiboChat - Production Ready
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio
import traceback

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

# Import modules
from recommender import client, MODEL, load_profile, load_all_profiles
from chat.service import chat_one_turn
from memory.service import get_memory_snapshot
from recommender_engine.service import index_products as re_index_products

# --- Logging Setup ---
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "zibochat_api.log"

logger = logging.getLogger("zibochat.api")
if not logger.handlers:
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.setLevel(logging.DEBUG)

# --- FastAPI App ---
app = FastAPI(
    title="ZiboChat API",
    description="API for ZiboChat - Production Ready",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # در production محدود کنید
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class UserProfile(BaseModel):
    user_id: str
    skin_type: Optional[str] = None
    age: Optional[int] = None
    skin_concerns: Optional[List[str]] = None
    preferences: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class ChatMessage(BaseModel):
    user_id: str
    # chat_id جدید؛ chat_room_id برای سازگاری عقب‌رو
    chat_id: Optional[str] = None
    chat_room_id: Optional[str] = "default"
    message: str
    timestamp: Optional[str] = None

class ChatResponse(BaseModel):
    user_id: str
    chat_id: str
    chat_room_id: str
    response: str
    recommended_products: Optional[List[Dict[str, Any]]] = None
    intent: Optional[str] = None
    priority_used: Optional[int] = None
    timestamp: str
    success: bool = True
    error: Optional[str] = None

class ConversationHistory(BaseModel):
    user_id: str
    chat_id: str
    chat_room_id: str
    messages: List[Dict[str, Any]]
    total_count: int

# --- Global State Management ---
# Cache برای پروفایل‌ها
_profile_cache: Dict[str, UserProfile] = {}
_conversation_cache: Dict[str, List[Dict[str, Any]]] = {}

def get_conversation_key(user_id: str, chat_id: Optional[str] = None, chat_room_id: str = "default") -> str:
    """کلید یکتا برای مکالمه (ترجیح chat_id)."""
    cid = chat_id or chat_room_id or "default"
    return f"{user_id}:{cid}"

def get_or_create_conversation(user_id: str, chat_id: Optional[str] = None, chat_room_id: str = "default") -> List[Dict[str, Any]]:
    """دریافت یا ایجاد مکالمه با chat_id."""
    key = get_conversation_key(user_id, chat_id=chat_id, chat_room_id=chat_room_id)
    if key not in _conversation_cache:
        _conversation_cache[key] = []
    return _conversation_cache[key]

# --- API Endpoints ---

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "ZiboChat API is running", "status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/health")
async def health_check():
    """Detailed health check"""
    try:
        # بررسی اتصال به OpenAI
        models = client.models.list()
        model_count = len(models.data) if hasattr(models, 'data') else 0
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "openai_connected": True,
            "available_models": model_count,
            "cache_size": len(_profile_cache),
            "active_conversations": len(_conversation_cache)
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@app.get("/api/v1/profile/{user_id}")
async def get_user_profile(user_id: str):
    """دریافت پروفایل کاربر"""
    try:
        # بررسی cache اول
        if user_id in _profile_cache:
            profile = _profile_cache[user_id]
            logger.info(f"Profile cache hit for user_id={user_id}")
            return profile
        
        # تلاش برای بارگذاری از Excel
        try:
            # فرض می‌کنیم user_id یک index است
            profile_index = int(user_id) if user_id.isdigit() else 0
            profile_data = load_profile(profile_index)
            
            # تبدیل به UserProfile
            profile = UserProfile(
                user_id=user_id,
                skin_type=profile_data.get("skin_type") or profile_data.get("نوع پوست"),
                age=profile_data.get("age") or profile_data.get("سن"),
                skin_concerns=profile_data.get("skin_concerns", []),
                preferences=profile_data,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
            
            # ذخیره در cache
            _profile_cache[user_id] = profile
            logger.info(f"Profile loaded from Excel for user_id={user_id}")
            return profile
            
        except Exception as e:
            logger.warning(f"Failed to load profile from Excel for user_id={user_id}: {e}")
            
            # ایجاد پروفایل پیش‌فرض
            default_profile = UserProfile(
                user_id=user_id,
                skin_type="mixed",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
            _profile_cache[user_id] = default_profile
            logger.info(f"Default profile created for user_id={user_id}")
            return default_profile
            
    except Exception as e:
        logger.error(f"Error getting profile for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"خطا در دریافت پروفایل: {str(e)}")

@app.post("/api/v1/profile/{user_id}")
async def update_user_profile(user_id: str, profile: UserProfile):
    """به‌روزرسانی پروفایل کاربر"""
    try:
        profile.user_id = user_id
        profile.updated_at = datetime.now().isoformat()
        _profile_cache[user_id] = profile
        
        logger.info(f"Profile updated for user_id={user_id}")
        return {"message": "پروفایل با موفقیت به‌روزرسانی شد", "user_id": user_id}
        
    except Exception as e:
        logger.error(f"Error updating profile for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"خطا در به‌روزرسانی پروفایل: {str(e)}")

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_with_user(chat_message: ChatMessage, background_tasks: BackgroundTasks):
    """ارسال پیام و دریافت پاسخ"""
    try:
        user_id = chat_message.user_id
        chat_id = chat_message.chat_id or chat_message.chat_room_id or "default"
        chat_room_id = chat_message.chat_room_id or chat_id or "default"
        message = chat_message.message.strip()
        
        if not message:
            raise HTTPException(status_code=400, detail="پیام نمی‌تواند خالی باشد")
        
        logger.info(f"Chat request: user_id={user_id}, chat_id={chat_id}, chat_room_id={chat_room_id}, message='{message[:100]}'")
        
        # دریافت پروفایل کاربر
        profile_data = await get_user_profile(user_id)
        profile_dict = profile_data.dict() if hasattr(profile_data, 'dict') else profile_data
        
        # دریافت مکالمه جاری
        conversation = get_or_create_conversation(user_id, chat_id=chat_id, chat_room_id=chat_room_id)
        
        # اضافه کردن پیام کاربر به مکالمه
        user_msg = {
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat()
        }
        conversation.append(user_msg)
        
        # تولید پاسخ
        try:
            answer, log = chat_one_turn(
                user_id=user_id,
                chat_id=chat_id,
                message=message,
                profile=profile_dict,
                max_count=5,
            )
            
            # اضافه کردن پاسخ به مکالمه
            bot_msg = {
                "role": "assistant", 
                "content": answer,
                "timestamp": datetime.now().isoformat()
            }
            conversation.append(bot_msg)
            
            # ذخیره تعامل در حافظه (background task)
            # interaction persisted inside chat_one_turn
            
            # آماده‌سازی پاسخ
            response = ChatResponse(
                user_id=user_id,
                chat_id=chat_id,
                chat_room_id=chat_room_id,
                response=answer,
                recommended_products=log.get("recommended_products", []),
                intent=log.get("intent"),
                priority_used=log.get("priority_used"),
                timestamp=datetime.now().isoformat(),
                success=True
            )
            
            logger.info(f"Chat response generated for user_id={user_id}, intent={log.get('intent')}")
            return response
            
        except Exception as e:
            logger.error(f"Error generating response for user_id={user_id}: {e}")
            logger.error(traceback.format_exc())
            
            # پاسخ خطا
            error_response = ChatResponse(
                user_id=user_id,
                chat_id=chat_id,
                chat_room_id=chat_room_id,
                response="متأسفانه خطایی در تولید پاسخ رخ داد. لطفاً دوباره تلاش کنید.",
                timestamp=datetime.now().isoformat(),
                success=False,
                error=str(e)
            )
            return error_response
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"خطای غیرمنتظره: {str(e)}")

@app.get("/api/v1/conversation/{user_id}")
async def get_conversation_history(user_id: str, chat_id: Optional[str] = None, chat_room_id: str = "default", limit: int = 50):
    """دریافت تاریخچه مکالمه"""
    try:
        conversation = get_or_create_conversation(user_id, chat_id=chat_id, chat_room_id=chat_room_id)
        
        # محدود کردن تعداد پیام‌ها
        recent_messages = conversation[-limit:] if limit > 0 else conversation
        
        return ConversationHistory(
            user_id=user_id,
            chat_id=chat_id or chat_room_id or "default",
            chat_room_id=chat_room_id,
            messages=recent_messages,
            total_count=len(conversation)
        )
        
    except Exception as e:
        logger.error(f"Error getting conversation for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"خطا در دریافت تاریخچه مکالمه: {str(e)}")

@app.delete("/api/v1/conversation/{user_id}")
async def clear_conversation_history(user_id: str, chat_id: Optional[str] = None, chat_room_id: str = "default"):
    """پاک کردن تاریخچه مکالمه"""
    try:
        key = get_conversation_key(user_id, chat_id=chat_id, chat_room_id=chat_room_id)
        if key in _conversation_cache:
            del _conversation_cache[key]
        
        logger.info(f"Conversation cleared for user_id={user_id}, chat_id={chat_id}, chat_room_id={chat_room_id}")
        return {"message": "تاریخچه مکالمه پاک شد", "user_id": user_id, "chat_id": chat_id or chat_room_id or "default", "chat_room_id": chat_room_id}
        
    except Exception as e:
        logger.error(f"Error clearing conversation for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"خطا در پاک کردن تاریخچه: {str(e)}")

@app.get("/api/v1/memory/{user_id}")
async def get_user_memory_summary(user_id: str):
    """دریافت خلاصه حافظه کاربر"""
    try:
        snap = get_memory_snapshot(user_id)
        return {"user_id": user_id, "memory_summary": snap.get("summary"), "recent_context": snap.get("recent_context"), "timestamp": datetime.now().isoformat()}
        
    except Exception as e:
        logger.error(f"Error getting memory for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"خطا در دریافت حافظه: {str(e)}")

@app.post("/api/v1/admin/index-products")
async def index_products():
    """ایندکس کردن محصولات به FAISS (admin endpoint)"""
    try:
        count = re_index_products()
        logger.info(f"Products indexed: {count}")
        return {"message": f"{count} محصول ایندکس شد", "count": count}
        
    except Exception as e:
        logger.error(f"Error indexing products: {e}")
        raise HTTPException(status_code=500, detail=f"خطا در ایندکس محصولات: {str(e)}")

@app.get("/api/v1/stats")
async def get_stats():
    """آمار سیستم"""
    try:
        return {
            "cached_profiles": len(_profile_cache),
            "active_conversations": len(_conversation_cache),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=f"خطا در دریافت آمار: {str(e)}")

# --- Error Handlers ---
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Endpoint not found", "path": str(request.url)}
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )

# --- Startup Event ---
@app.on_event("startup")
async def startup_event():
    """رویداد راه‌اندازی"""
    logger.info("ZiboChat API starting up...")
    
    # بررسی اتصال به OpenAI
    try:
        models = client.models.list()
        logger.info(f"Connected to OpenAI, {len(models.data)} models available")
    except Exception as e:
        logger.error(f"Failed to connect to OpenAI: {e}")
    
    logger.info("ZiboChat API startup completed")

# --- Main ---
if __name__ == "__main__":
    # تنظیمات سرور
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8001))
    workers = int(os.getenv("WORKERS", 1))
    
    logger.info(f"Starting ZiboChat API on {host}:{port}")
    
    uvicorn.run(
        "api:app",
        host=host,
        port=port,
        workers=workers,
        reload=False,  # در production باید False باشد
        log_level="info"
    )

