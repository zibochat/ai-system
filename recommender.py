import json
import os
from pathlib import Path
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List

# --- Load ENV (robust) ---
# Try to locate .env relative to this file to avoid CWD issues
BASE_DIR = Path(__file__).resolve().parent
env_file = find_dotenv(usecwd=True) or str(BASE_DIR / ".env")
load_dotenv(env_file, override=True)

API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = os.getenv("OPENAI_BASE_URL")
TEAM_ID = os.getenv("LIARA_TEAM_ID") or os.getenv("TEAM_ID") or os.getenv("LIARA_TEAM")
MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini")

if not API_KEY:
    raise RuntimeError("OPENAI_API_KEY not loaded. Ensure it exists in .env or environment variables.")

def _debug_check_models(client):
    try:
        models = client.models.list()
        names = [m.id for m in models.data][:20]
        print("[DEBUG] Models available:", names)
    except Exception as e:
        print("[DEBUG] list models failed:", repr(e))

extra_headers = {}
if TEAM_ID:
    extra_headers["x-teamid"] = TEAM_ID

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL.rstrip("/") if BASE_URL else None,
    default_headers=extra_headers if extra_headers else None
)

# Run the check once when module loads (can be disabled by env flag)
if os.getenv("DEBUG_AI", "0") == "1":
    _debug_check_models(client)

# --- Load data ---
def load_data():
    with open("data/products.json", encoding="utf-8") as f:
        prod_raw = json.load(f)
        products = prod_raw[2]["data"]

    with open("data/comments.json", encoding="utf-8") as f:
        comm_raw = json.load(f)
        comments = comm_raw[2]["data"]

    return products, comments

# --- Read user profile from Excel ---
_PROFILE_CACHE: Dict[str, Any] = {}
def _load_profiles_df():
    if "df" not in _PROFILE_CACHE:
        _PROFILE_CACHE["df"] = pd.read_excel("data/shenakht_poosti.xlsx")
    return _PROFILE_CACHE["df"]

def load_profile(row_index=0):
    df = _load_profiles_df()
    if row_index < 0 or row_index >= len(df):
        raise IndexError("profile index out of range")
    return df.iloc[row_index].to_dict()

def load_all_profiles(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    df = _load_profiles_df()
    rows = df.to_dict(orient="records")
    return rows if limit is None else rows[:limit]

# --- Summarize comments ---
def summarize_comments(product_id, comments):
    related = [c for c in comments if c["product_id"] == str(product_id)]
    if not related:
        return "هیچ نظری برای این محصول ثبت نشده."

    joined = "\n".join([c["description"] for c in related[:10]])
    prompt = f"""
    تو یک متخصص پوست هستی.
    نظرات زیر مربوط به یک محصول مراقبت پوستی است.
    خلاصه‌ای کوتاه بده: 
    - نکات مثبت
    - نکات منفی
    - مناسب چه کسانی
    - نامناسب برای چه کسانی

    نظرات:
    {joined}
    """
    try:
        model_to_use = MODEL
        if os.getenv("DEBUG_AI", "0") == "1":
            print(f"[DEBUG] summarize using model: {model_to_use} base_url={BASE_URL} team={TEAM_ID}")
        resp = client.chat.completions.create(
            model=model_to_use,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        # Provide clearer guidance for 404 workspace/model issues
        msg = str(e)
        hints = []
        if "404" in msg or "workspace" in msg.lower():
            hints.append("بررسی کن Base URL دقیقاً همان مقدار مستند لیارا باشد (با workspace id).")
            hints.append("هدر x-teamid باید ست شود (الان: %s)." % (TEAM_ID or "None"))
        if "model" in msg.lower():
            hints.append("لیست مدل‌ها را با فعال کردن DEBUG_AI=1 ببین.")
        raise RuntimeError("خطا در summarize_comments: " + msg + "\nراهنما: " + " | ".join(hints)) from e

# --- Recommend routine ---
def recommend(profile, user_message, max_count=5):
    products, comments = load_data()

    # --- جدا کردن محصولات با کامنت و بدون کامنت ---
    products_with_comments = [p for p in products if any(c["product_id"] == str(p["id"]) for c in comments)]
    products_without_comments = [p for p in products if p not in products_with_comments]

    # --- انتخاب کاندیدها با اولویت محصولات با کامنت ---
    candidates = products_with_comments[:max_count]
    if len(candidates) < max_count:
        remaining = max_count - len(candidates)
        candidates += products_without_comments[:remaining]

    summaries = []
    fallback_to_profile = False

    if candidates:
        for p in candidates:
            related_comments = [c for c in comments if c["product_id"] == str(p["id"])]
            if related_comments:
                s = summarize_comments(p["id"], comments)
            else:
                # اگر کامنت نبود، خلاصه‌ای کوتاه از محصول بساز (مثلاً نام + نوع محصول)
                s = f"محصول بدون نظر ثبت شده، نام: {p.get('nameFa', p.get('nameEn',''))}"
            summaries.append({"id": p["id"], "name": p.get('nameFa', p.get('nameEn', '')) , "summary": s})
    else:
        fallback_to_profile = True

    # --- آماده کردن پرامپت ---
    if summaries:
        prompt = f"""
پروفایل کاربر:
{json.dumps(profile, ensure_ascii=False)}

پیام کاربر:
{user_message}

محصولات کاندید:
{json.dumps(summaries, ensure_ascii=False)}

توجه: محصولاتی که دارای نظرات واقعی هستند اولویت دارند و خلاصه نظراتشان ارائه شده است.
محصولاتی بدون نظر فقط به عنوان جایگزین در نظر گرفته شوند.
لطفاً محصولات مناسب برای کاربر را انتخاب کن و دلیل انتخاب را توضیح بده.
"""
    else:
        fallback_to_profile = True
        prompt = f"""
پروفایل کاربر:
{json.dumps(profile, ensure_ascii=False)}

پیام کاربر:
{user_message}

هیچ محصول مرتبطی در دیتابیس موجود نیست.
لطفاً بر اساس مشخصات پوست و اطلاعات عمومی، توصیه‌هایی بده.
"""

    # --- فراخوانی مدل ---
    try:
        model_to_use = MODEL
        resp = client.chat.completions.create(
            model=model_to_use,
            messages=[
                {"role": "system", "content": "تو یک مشاور حرفه‌ای پوست هستی."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )
        answer = resp.choices[0].message.content.strip()

        # --- لاگ ---
        log = {
            "used_products": [p.get("name", p.get("nameFa", "")) for p in summaries if any(c["product_id"] == str(p["id"]) for c in comments)],
            "fallback_to_profile": fallback_to_profile,
            "user_message": user_message,
            "profile": profile
        }
        return answer, log
    except Exception as e:
        raise RuntimeError("خطا در recommend: " + str(e)) from e

# ================= FastAPI =================
app = FastAPI(title="ZiboChat Recommender", version="0.1.0")

class ChatRequest(BaseModel):
    profile_id: Optional[int] = Field(None, description="Index of profile row in Excel")
    profile: Optional[Dict[str, Any]] = Field(None, description="Explicit profile payload; overrides profile_id if set")
    message: str = Field(..., description="User message")
    max_products: int = Field(5, ge=1, le=20)

class ChatResponse(BaseModel):
    answer: str
    model: str
    used_profile: Dict[str, Any]
    used_products: List[str] = []
    fallback_to_profile: bool

@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL}

@app.get("/profiles")
def list_profiles(limit: int | None = None):
    try:
        items = load_all_profiles(limit=limit)
        return {"count": len(items), "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/profiles/{profile_id}")
def get_profile(profile_id: int):
    try:
        return load_profile(profile_id)
    except IndexError:
        raise HTTPException(status_code=404, detail="profile not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.profile and req.profile_id is None:
        raise HTTPException(status_code=400, detail="profile or profile_id required")
    try:
        prof = req.profile if req.profile is not None else load_profile(req.profile_id)  # type: ignore
        answer, log = recommend(prof, req.message, max_count=req.max_products)
        return ChatResponse(
            answer=answer,
            model=MODEL,
            used_profile=prof,
            used_products=log.get("used_products", []),
            fallback_to_profile=log.get("fallback_to_profile", False)
        )
    except IndexError:
        raise HTTPException(status_code=404, detail="profile not found")
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/models")
def models():
    try:
        data = client.models.list()
        return {"models": [m.id for m in data.data]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Run with: uvicorn recommender:app --reload
