import json
import os
from pathlib import Path
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
import io
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
import logging
import traceback

# --- Load ENV (robust) ---
# Try to locate .env relative to this file to avoid CWD issues
BASE_DIR = Path(__file__).resolve().parent
env_file = find_dotenv(usecwd=True) or str(BASE_DIR / ".env")
# Load .env and sanitize
load_dotenv(env_file, override=True)

def _strip_env(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    return v

API_KEY = _strip_env(os.getenv("OPENAI_API_KEY"))
BASE_URL = _strip_env(os.getenv("OPENAI_BASE_URL"))
#TEAM_ID = os.getenv("LIARA_TEAM_ID") or os.getenv("TEAM_ID") or os.getenv("LIARA_TEAM")
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
# if TEAM_ID:
#     extra_headers["x-teamid"] = TEAM_ID

# Clear common proxy env vars to avoid httpx picking up a proxy and causing TLS/proxy errors
for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"):
    os.environ.pop(k, None)

# Create OpenAI client after sanitization
client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL.rstrip("/") if BASE_URL else None,
    default_headers=extra_headers if extra_headers else None
)

# logging
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "zibochat.log"
logger = logging.getLogger("zibochat.recommender")
if not logger.handlers:
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.setLevel(logging.DEBUG)

# Run the check once when module loads (can be disabled by env flag)
if os.getenv("DEBUG_AI", "0") == "1":
    _debug_check_models(client)

# Optional LangChain/FAISS integration helper
USE_LANGCHAIN = os.getenv("USE_LANGCHAIN", "0") in ("1", "true", "True")
llm_agent = None
if USE_LANGCHAIN:
    try:
        # local helper module that wraps langchain/FAISS usage (optional)
        import llm_agent as _llm_agent
        llm_agent = _llm_agent
    except Exception as e:
        print(f"WARNING: USE_LANGCHAIN is set but failed to import llm_agent: {e}")

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


def index_products_to_faiss(user_index_id: str = "products_index", embeddings_model: Optional[str] = None, force: bool = False):
    """Create/persist a FAISS index containing one document per product that includes product metadata and concatenated comments.
    Uses the optional llm_agent.upsert_user_docs helper (requires LangChain/faiss installed)."""
    # import llm_agent dynamically to avoid relying on module-level variable set at import time
    try:
        import llm_agent as _llm_agent
    except Exception:
        raise RuntimeError("LangChain/llm_agent not available. Enable USE_LANGCHAIN or install langchain and faiss-cpu.")

    products, comments = load_data()
    docs = []
    for p in products:
        pid = str(p.get("id"))
        name = p.get("nameFa") or p.get("nameEn") or p.get("name") or ""
        desc = p.get("description", "") or ""
        related = [c for c in comments if c.get("product_id") == pid]
        joined_comments = "\n".join([f"- {c.get('description','')[:1000]}" for c in related])
        text = f"Product: {name}\nID: {pid}\nDescription:\n{desc}\n\nComments:\n{joined_comments}"
        docs.append({"id": f"product_{pid}", "text": text, "meta": {"type": "product", "product_id": pid, "name": name}})

    # upsert into per-index user_id
    _llm_agent.upsert_user_docs(user_index_id, docs, embeddings_model=embeddings_model)
    return len(docs)

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
    # If optional langchain agent is available, prefer it (it can use FAISS retrieval)
    if llm_agent is not None:
        try:
            return llm_agent.chat_with_context(
                messages=[
                    {"role": "system", "content": "خلاصه‌ای کوتاه درباره نظرات محصول به فارسی؛ فقط نکات مهم."},
                    {"role": "user", "content": prompt},
                ],
                model=MODEL,
            )
        except Exception as e:
            print(f"llm_agent.chat_with_context failed, falling back to direct client: {e}")

    try:
        model_to_use = MODEL
        if os.getenv("DEBUG_AI", "0") == "1":
            print(f"[DEBUG] summarize using model: {model_to_use} base_url={BASE_URL} t")
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
            team = os.getenv("LIARA_TEAM_ID") or os.getenv("TEAM_ID") or os.getenv("LIARA_TEAM")
            hints.append("هدر x-teamid باید ست شود (الان: %s)." % (team or "None"))
        if "model" in msg.lower():
            hints.append("لیست مدل‌ها را با فعال کردن DEBUG_AI=1 ببین.")
    logger.exception('summarize_comments failed: %s', msg)
    raise RuntimeError("خطا در summarize_comments: " + msg + "\nراهنما: " + " | ".join(hints)) from e

# --- Recommend routine ---
def recommend(profile, user_message, max_count=5):
    products, comments = load_data()
    # --- تعیین وضعیت موجودی (اگر در داده‌ها وجود داشته باشد) ---
    def _is_available(prod: dict) -> Optional[bool]:
        # try common inventory fields; return None if unknown
        for k in ("in_stock", "is_available", "available", "stock", "quantity", "qty"):
            v = prod.get(k)
            if v is None:
                continue
            # numeric counts
            try:
                if isinstance(v, (int, float)):
                    return bool(v)
                s = str(v).strip()
                if s == "":
                    continue
                if s.isdigit():
                    return int(s) > 0
                if s.lower() in ("true", "yes", "1"): 
                    return True
                if s.lower() in ("false", "no", "0"):
                    return False
            except Exception:
                continue
        return None

    # mark each product with has_comments and availability (if detectable)
    for p in products:
        p["_has_comments"] = any(c["product_id"] == str(p["id"]) for c in comments)
        p["_available"] = _is_available(p)

    # --- مرتب‌سازی کاندیدها بر اساس اولویت:
    # 1) محصولات دارای کامنت (اولویت بالا)
    # 2) محصولات موجود (در صورت قابل‌تشخیص بودن موجودی)
    # در صورت عدم وجود اطلاعات موجودی، محصولات را به عنوان 'مشخص‌نشده' در نظر می‌گیریم و آن‌ها را پایین‌تر از موارد مشخص‌شده موجود قرار می‌دهیم.
    def _sort_key(prod: dict):
        # has_comments True first -> sort by 1/0
        has_comments = 1 if prod.get("_has_comments") else 0
        avail = prod.get("_available")
        # availability: True > None > False
        if avail is True:
            a_score = 2
        elif avail is None:
            a_score = 1
        else:
            a_score = 0
        return (has_comments, a_score)

    products_sorted = sorted(products, key=_sort_key, reverse=True)
    candidates = products_sorted[:max_count]

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
        # If llm_agent available, use it to allow vector retrieval
        if llm_agent is not None:
            try:
                answer = llm_agent.chat_with_context(
                    messages=[
                        {"role": "system", "content": "تو یک مشاور حرفه‌ای پوست هستی."},
                        {"role": "user", "content": prompt}
                    ],
                    model=model_to_use,
                )
            except Exception as e:
                print(f"llm_agent.chat_with_context failed, falling back to direct client: {e}")
                answer = ""
        else:
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
        logger.exception('recommend failed: %s', e)
        raise RuntimeError("خطا در recommend: " + str(e)) from e

