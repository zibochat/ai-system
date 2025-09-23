import json
import os
from pathlib import Path
import pandas as pd
from openai import OpenAI
import httpx
from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
import io
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
import re
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
    default_headers=extra_headers if extra_headers else None,
    # avoid using system proxies; use sane TLS; bump timeout
    http_client=httpx.Client(trust_env=False, verify=True, timeout=30.0),
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
RAG_STRICT = os.getenv("RAG_STRICT", "1") in ("1", "true", "True")
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


_DEF_FACE_WORDS = ["صورت", "face", "چهره", "facial"]
_DEF_BODY_WORDS = ["بدن", "body", "لوسیون بدن", "body lotion", "دست", "پا"]


def _infer_face_or_body(name: str, desc: str) -> str:
    text = (name or "") + " " + (desc or "")
    tl = text.lower()
    if any(w in tl for w in [w.lower() for w in _DEF_BODY_WORDS]) and not any(w in tl for w in [w.lower() for w in _DEF_FACE_WORDS]):
        return "body"
    if any(w in tl for w in [w.lower() for w in _DEF_FACE_WORDS]):
        return "face"
    return "unknown"


# --- Products summaries from FAISS products_index (cached) ---
_PRODUCT_INDEX_META_CACHE: Dict[str, Any] = {}
def _load_products_index_meta() -> Dict[str, Any]:
    if _PRODUCT_INDEX_META_CACHE:
        return _PRODUCT_INDEX_META_CACHE
    try:
        meta_path = BASE_DIR / "data" / "faiss" / "products_index" / "meta.json"
        if meta_path.exists():
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            _PRODUCT_INDEX_META_CACHE.update(data)
    except Exception as e:
        logger.exception('failed to load products_index meta: %s', e)
    return _PRODUCT_INDEX_META_CACHE

def _get_product_summary_from_index(product_id: str | int) -> Optional[str]:
    meta = _load_products_index_meta()
    if not meta:
        return None
    pid = str(product_id)
    # default ID pattern used by indexer
    key = f"product_{pid}"
    if key in meta:
        try:
            text = meta[key].get("text")
            if isinstance(text, str) and text.strip():
                # If the stored text is long raw content, keep a reasonable slice
                return text.strip()
        except Exception:
            pass
    # fallback: scan over entries to match meta.product_id
    try:
        for doc_id, doc in meta.items():
            m = doc.get("meta", {})
            if str(m.get("product_id")) == pid:
                t = doc.get("text", "").strip()
                if t:
                    return t
    except Exception:
        pass
    return None


# --- Helpers ---
def _strip_redundant_greeting(text: str) -> str:
    """Remove leading greetings like 'سلام' when not necessary."""
    if not isinstance(text, str):
        return text
    # Remove leading spaces and common punctuation/emoji
    t = text.lstrip()
    t = re.sub(r'^[\s\u200c\u200f\ufeff\u2066\u2067\u2068\u2069\W_]+', '', t, flags=re.UNICODE)
    # Remove a leading greeting token if present
    patterns = [
        r'^(سلام(\s*و\s*وقت\s*بخیر)?)([\s\W_]+)?',
        r'^(درود)([\s\W_]+)?',
        r'^(hi|hello|hey)([\s\W_]+)?',
    ]
    out = t
    for pat in patterns:
        out_new = re.sub(pat, '', out, flags=re.IGNORECASE)
        if out_new != out:
            out = out_new
            break
    out = out.lstrip(' ،:!-—.\n\r\t')
    return out if out else text


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
        name = p.get("fullName") or p.get("full_name") or p.get("nameFa") or p.get("nameEn") or p.get("name") or ""
        desc = p.get("description", "") or ""
        category = p.get("category") or p.get("type") or ""
        tags = p.get("tags") or []
        related = [c for c in comments if c.get("product_id") == pid]
        joined_comments = "\n".join([f"- {c.get('description','')[:700]}" for c in related[:20]])
        face_or_body = _infer_face_or_body(name, desc)
        # Enrich the text for better retrieval and faster non-LLM summarization
        text = (
            f"Name: {name}\n"
            f"ID: {pid}\n"
            f"Category: {category}\n"
            f"Tags: {', '.join(map(str, tags))}\n"
            f"For: {face_or_body}\n"
            f"Description:\n{desc}\n\n"
            f"Comments (sample):\n{joined_comments}"
        )
        meta = {"type": "product", "product_id": pid, "name": name, "category": category, "tags": tags, "for": face_or_body}
        docs.append({"id": f"product_{pid}", "text": text, "meta": meta})

    # upsert into per-index user_id
    _llm_agent.upsert_user_docs(user_index_id, docs, embeddings_model=embeddings_model)
    return len(docs)

# --- Summarize comments ---

def _fast_summary_from_index_or_comments(product_id: str | int, comments: List[dict]) -> str:
    # prefer the index text if available (already contains desc + sample comments)
    idx_text = _get_product_summary_from_index(product_id)
    if isinstance(idx_text, str) and idx_text.strip():
        # Build a short extractive snippet
        lines = [ln.strip() for ln in idx_text.splitlines() if ln.strip()]
        # take name/category/for + first 3 bullets from comments
        header = []
        for key in ("Name:", "Category:", "For:"):
            for ln in lines:
                if ln.startswith(key):
                    header.append(ln)
                    break
        bullets = [ln for ln in lines if ln.startswith("-")][:3]
        body = "\n".join(bullets) if bullets else ""
        out = "\n".join(header + ([""] if body else []) + (["نکات (برگرفته از نظرات):"] if body else []) + ([body] if body else []))
        return out.strip() or (lines[0] if lines else "")

    # fallback: summarize from first few comments without LLM
    related = [c for c in comments if c.get("product_id") == str(product_id)]
    if not related:
        return ""
    sample = [c.get("description", "") for c in related[:5] if c.get("description")]
    joined = " ".join(sample)[:800]
    return f"نکات از نظرات: {joined}"


def summarize_comments(product_id, comments):
    # Fast path, no-LLM
    fast = _fast_summary_from_index_or_comments(product_id, comments)
    if fast:
        return fast
    # final minimal fallback
    return "هیچ نظری برای این محصول ثبت نشده."

# --- Recommend routine ---
def recommend(profile, user_message, max_count=5, user_id: Optional[str] = None):
    # تشخیص سلام و احوالپرسی و پاسخ دوستانه بدون توصیه محصول
    def _is_greeting(text: str) -> bool:
        t = (text or "").strip().lower()
        t_compact = re.sub(r"[\s،,.!?:;~\-–—]+", " ", t).strip()
        greetings = {"سلام", "درود", "وقت بخیر", "صبح بخیر", "شب بخیر", "hi", "hello", "hey", "salam", "سلاممم"}
        tokens = t_compact.split()
        return 0 < len(tokens) <= 2 and all(tok in greetings for tok in tokens)

    if _is_greeting(user_message):
        try:
            model_to_use = MODEL
            answer = None
            if llm_agent is not None:
                try:
                    answer = llm_agent.chat_with_context(
                        messages=[
                            {"role": "system", "content": "تو یک مشاور حرفه‌ای پوست هستی. با لحن دوستانه و کوتاه پاسخ بده و اگر مکالمه جاری است از سلام مجدد خودداری کن."},
                            {"role": "user", "content": user_message}
                        ],
                        model=model_to_use,
                        user_id=user_id,
                        use_memory=True,
                    )
                except Exception:
                    answer = None
            if not answer:
                try:
                    resp = client.chat.completions.create(
                        model=model_to_use,
                        messages=[
                            {"role": "system", "content": "تو یک مشاور حرفه‌ای پوست هستی. با لحن دوستانه و کوتاه پاسخ بده و اگر مکالمه جاری است از سلام مجدد خودداری کن."},
                            {"role": "user", "content": user_message}
                        ],
                        temperature=0.5
                    )
                    answer = resp.choices[0].message.content.strip()
                except Exception as e:
                    logger.exception('greeting primary client failed: %s', e)
                    # HTTP fallback
                    if BASE_URL and API_KEY:
                        try:
                            import httpx
                            url = BASE_URL.rstrip("/") + "/chat/completions"
                            headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
                            body = {
                                "model": model_to_use,
                                "messages": [
                                    {"role": "system", "content": "تو یک مشاور حرفه‌ای پوست هستی. با لحن دوستانه و کوتاه پاسخ بده."},
                                    {"role": "user", "content": user_message}
                                ],
                                "temperature": 0.5,
                            }
                            r = httpx.post(url, json=body, headers=headers, timeout=20.0, verify=True, trust_env=False)
                            r.raise_for_status()
                            data = r.json()
                            answer = data.get("choices", [])[0].get("message", {}).get("content", "").strip()
                        except Exception as e2:
                            logger.exception('greeting HTTP fallback failed: %s', e2)
            log = {
                "priority_used": 0,
                "recommended_product_ids": [],
                "recommended_products": [],
                "intent": "greeting",
                "user_message": user_message,
                "profile": profile,
            }
            # remove redundant greeting if conversation is ongoing + log diagnostics
            if llm_agent is not None and user_id:
                try:
                    mem = llm_agent.get_conversation_context(user_id, num_messages=1)
                    orig = answer
                    stripped = False
                    if mem:
                        new_ans = _strip_redundant_greeting(answer)
                        stripped = (new_ans != answer)
                        answer = new_ans
                    logger.info(
                        "chat:greeting user_id=%s mem_present=%s stripped=%s user='%s' ans_before='%s' ans_after='%s'",
                        user_id, bool(mem), stripped, str(user_message)[:80], str(orig)[:120], str(answer)[:120]
                    )
                except Exception as e:
                    logger.exception('postprocess greeting failed: %s', e)
            return answer, log
        except Exception as e:
            logger.exception('greeting chat failed: %s', e)
            raise

    products, comments = load_data()

    # اگر کاربر نیتِ «پیشنهاد محصول» ندارد، فقط مکالمه انجام بده
    def _is_product_intent(text: str) -> bool:
        t = (text or "").lower()
        product_words = [
            "محصول", "پیشنهاد", "توصیه", "بخرم", "چی خوبه", "recommend", "suggest",
            "سرم", "کرم", "ضد آفتاب", "شوینده", "تونر", "mask", "ماسک", "moisturizer"
        ]
        return any(w in t for w in product_words)

    if not _is_product_intent(user_message):
        # پاسخ مکالمه‌ای کوتاه با استفاده از پروفایل، بدون توصیه محصول
        conv_prompt = f"""
پروفایل کاربر:
{json.dumps(profile, ensure_ascii=False)}

سؤال کاربر:
{user_message}

پاسخی دوستانه و کوتاه بده. اگر لازم است یک سؤال روشن‌ساز بپرس. از معرفی محصول خودداری کن مگر اینکه کاربر صراحتاً درخواست محصول کند.
"""
        try:
            model_to_use = MODEL
            answer = None
            if llm_agent is not None:
                try:
                    answer = llm_agent.chat_with_context(
                        messages=[
                            {"role": "system", "content": "تو یک مشاور حرفه‌ای پوست هستی. اگر مکالمه جاری است از سلام مجدد خودداری کن."},
                            {"role": "user", "content": conv_prompt}
                        ],
                        model=model_to_use,
                        user_id=user_id,
                        use_memory=True,
                    )
                except Exception:
                    answer = None
            if not answer:
                resp = client.chat.completions.create(
                    model=model_to_use,
                    messages=[
                        {"role": "system", "content": "تو یک مشاور حرفه‌ای پوست هستی."},
                        {"role": "user", "content": conv_prompt}
                    ],
                    temperature=0.5
                )
                answer = resp.choices[0].message.content.strip()
            log = {
                "intent": "conversation",
                "priority_used": None,
                "recommended_product_ids": [],
                "recommended_products": [],
                "user_message": user_message,
                "profile": profile,
            }
            if llm_agent is not None and user_id:
                try:
                    mem = llm_agent.get_conversation_context(user_id, num_messages=1)
                    orig = answer
                    stripped = False
                    if mem:
                        new_ans = _strip_redundant_greeting(answer)
                        stripped = (new_ans != answer)
                        answer = new_ans
                    logger.info(
                        "chat:conversation user_id=%s mem_present=%s stripped=%s user='%s' ans_before='%s' ans_after='%s'",
                        user_id, bool(mem), stripped, str(user_message)[:80], str(orig)[:120], str(answer)[:120]
                    )
                except Exception as e:
                    logger.exception('postprocess conversation failed: %s', e)
            return answer, log
        except Exception as e:
            logger.exception('conversation chat failed: %s', e)
            raise

    # --- تعیین وضعیت موجودی (اگر در داده‌ها وجود داشته باشد) ---
    def _is_available(prod: dict) -> Optional[bool]:
        for k in ("in_stock", "is_available", "available", "stock", "quantity", "qty"):
            v = prod.get(k)
            if v is None:
                continue
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

    # برچسب‌گذاری محصولات به داشتن نظر و موجودی
    for p in products:
        p["_has_comments"] = any(c["product_id"] == str(p["id"]) for c in comments)
        p["_available"] = _is_available(p)

    # --- تشخیص نیت کاربر و تطبیق سخت‌گیرانه‌تر ---
    def _detect_intent(text: str) -> Optional[str]:
        t = (text or "").lower()
        moist_words = ["مرطوب", "مرطوب کننده", "مرطوب‌کننده", "آبرسان", "moistur", "hydrating", "moisturizer", "hydration"]
        if any(w in t for w in moist_words):
            return "moisturizer"
        return None

    user_intent = _detect_intent(user_message)

    def _matches_intent(prod: dict, text: str, intent: Optional[str]) -> bool:
        name = ((prod.get("fullName") or prod.get("full_name") or "") + " " + (prod.get("nameFa") or "") + " " + (prod.get("nameEn") or "") + " " + (prod.get("name") or "")).lower()
        desc = str(prod.get("description") or "").lower()
        full = name + " " + desc
        # include category/type/tags if available for richer matching
        cat = (str(prod.get("category") or prod.get("type") or "") + " " + " ".join([str(t) for t in (prod.get("tags") or [])])).lower()
        full_meta = full + " " + cat
        t = (text or "").lower()

        if intent == "moisturizer":
            positive = ["مرطوب", "مرطوب کننده", "مرطوب‌کننده", "آبرسان", "moistur", "hydrating", "moisturizer", "hydration"]
            form_words = ["کرم", "cream", "ژل", "gel", "مرطوب کننده", "moisturizer"]
            negative = [
                "اسکراب", "scrub", "ماسک", "mask", "شوینده", "cleanser", "فوم", "تونر", "toner", "سرم", "serum", "صابون", "soap",
                # exclude body-only items
                "بدن", "body", "لوسیون بدن", "body lotion"
            ]
            # hard exclude negatives (e.g., body lotions)
            if any(n in full_meta for n in negative):
                return False
            # must be hydrating + a moisturizer form
            has_positive_mention_in_query = any(p in t for p in positive)
            has_positive_in_product = any(p in full_meta for p in positive)
            has_form = any(f in full_meta for f in form_words)
            return (has_positive_mention_in_query and has_positive_in_product and has_form)

        # پیش‌فرض: تطبیق آزادتر با همپوشانی واژه‌های عمومی مراقبت از پوست
        generic = ["sunscreen", "ضد آفتاب", "cleanser", "شوینده", "toner", "سرم", "serum", "mask", "ماسک", "کرم", "cream", "ژل", "gel", "آبرسان", "مرطوب کننده"]
        return any(k in t and k in full_meta for k in generic)

    # اگر FAISS/Embeddings در دسترس باشد، انتخاب محصولات مرتبط به صورت معنایی انجام شود
    intent_products: List[dict] = []
    try:
        if llm_agent is not None and llm_agent._langchain_available():
            # Enrich retrieval query with user profile to improve relevance
            try:
                profile_snippet = json.dumps(profile, ensure_ascii=False)[:800]
            except Exception:
                profile_snippet = ""
            retrieval_query = f"{user_message}\nپروفایل: {profile_snippet}" if profile_snippet else user_message
            k = 100 if RAG_STRICT else 50
            retrieved = llm_agent.retrieve_user_memory("products_index", retrieval_query, k=k)
            product_ids = []
            for r in retrieved:
                m = r.get("meta", {})
                pid = m.get("product_id")
                if not pid:
                    # attempt to parse from text header like "ID: <pid>"
                    try:
                        text = r.get("text", "")
                        import re as _re
                        m2 = _re.search(r"^ID:\s*(\d+)", text, flags=_re.MULTILINE)
                        if m2:
                            pid = m2.group(1)
                    except Exception:
                        pid = None
                if pid and str(pid) not in product_ids:
                    product_ids.append(str(pid))
            if product_ids:
                idset = set(product_ids)
                faiss_products = [p for p in products if str(p.get("id")) in idset]
                # Prefer FAISS results when strict mode is on
                if RAG_STRICT:
                    intent_products = faiss_products
                else:
                    intent_products = faiss_products
    except Exception as e:
        logger.exception('semantic retrieval failed, falling back to rule-based intent: %s', e)

    # اگر semantic نتیجه نداد، از قواعد ساده استفاده شود
    if not intent_products:
        intent_products = [p for p in products if _matches_intent(p, user_message, user_intent)]

    # اگر همچنان چیزی پیدا نشد، fallback به پرکامنترین محصولات مرتبط با صورت
    if not intent_products:
        # rank by number of comments (desc) and prefer face-oriented based on simple heuristics
        def _is_face(prod: dict) -> bool:
            text = (str(prod.get('fullName') or prod.get('full_name') or '') + ' ' + str(prod.get('nameFa') or '') + ' ' + str(prod.get('nameEn') or '') + ' ' + str(prod.get('description') or '')).lower()
            return any(w in text for w in ['صورت', 'face', 'facial', 'کرم', 'cream']) and not any(w in text for w in ['بدن', 'body', 'لوسیون بدن', 'body lotion'])
        # precompute comment counts
        pid_to_count = {}
        for c in comments:
            pid_to_count[str(c.get('product_id'))] = pid_to_count.get(str(c.get('product_id')), 0) + 1
        ranked = sorted(products, key=lambda p: pid_to_count.get(str(p.get('id')), 0), reverse=True)
        face_ranked = [p for p in ranked if _is_face(p)]
        intent_products = face_ranked[:max_count] if face_ranked else ranked[:max_count]

    # اولویت 1: دارای کامنت
    prio1 = [p for p in intent_products if p.get("_has_comments")]
    # اولویت 2: بدون کامنت
    prio2 = [p for p in intent_products if not p.get("_has_comments")]

    # مرتب‌سازی با توجه به موجودی
    def _score(prod: dict) -> int:
        avail = prod.get("_available")
        if avail is True:
            return 2
        if avail is None:
            return 1
        return 0

    prio1.sort(key=_score, reverse=True)
    prio2.sort(key=_score, reverse=True)

    chosen_priority = None
    candidates: List[dict] = []
    if prio1:
        candidates = prio1[:max_count]
        chosen_priority = 1
    elif prio2:
        candidates = prio2[:max_count]
        chosen_priority = 2
    else:
        candidates = []
        chosen_priority = 3

    # خلاصه‌سازی
    summaries = []
    if candidates:
        for p in candidates:
            summary_source = "faiss_index" if _get_product_summary_from_index(p["id"]) else ("comments" if p.get("_has_comments") else "no_comments")
            if summary_source in ("faiss_index", "comments"):
                s = summarize_comments(p["id"], comments)
            else:
                s = f"محصول بدون نظر ثبت‌شده، نام: {p.get('fullName', p.get('full_name', p.get('nameFa', p.get('nameEn', p.get('name','')))))}"
            summaries.append({
                "id": p["id"],
                "name": (p.get('fullName') or p.get('full_name') or p.get('nameFa') or p.get('nameEn') or p.get('name') or ""),
                "summary": s,
                "summary_source": summary_source
            })

    # پرامپت
    if chosen_priority in (1, 2) and summaries:
        prompt = f"""
پروفایل کاربر:
{json.dumps(profile, ensure_ascii=False)}

پیام کاربر:
{user_message}

محصولات منتخب (اولویت {chosen_priority}):
{json.dumps(summaries, ensure_ascii=False)}

لطفاً محصولات مناسب را معرفی کن، دلایل را توضیح بده و نکات مراقبت پوستی مرتبط را اضافه کن.
"""
    else:
        prompt = f"""
پروفایل کاربر:
{json.dumps(profile, ensure_ascii=False)}

پیام کاربر:
{user_message}

هیچ محصول مناسبی از دیتابیس داخلی یافت نشد. لطفاً بر اساس اطلاعات عمومی علمی مراقبت از پوست، پیشنهادهای کاربردی ارائه بده.
"""

    # فراخوانی مدل
    try:
        model_to_use = MODEL
        answer = None

        if llm_agent is not None:
            try:
                answer = llm_agent.chat_with_context(
                    messages=[
                        {"role": "system", "content": "تو یک مشاور حرفه‌ای پوست هستی."},
                        {"role": "user", "content": prompt}
                    ],
                    model=model_to_use,
                    user_id=user_id,
                    use_memory=True,
                )
            except Exception as e:
                logger.exception('llm_agent.chat_with_context failed: %s', e)

        if not answer:
            try:
                resp = client.chat.completions.create(
                    model=model_to_use,
                    messages=[
                        {"role": "system", "content": "تو یک مشاور حرفه‌ای پوست هستی."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.5
                )
                answer = resp.choices[0].message.content.strip()
            except Exception as e:
                logger.exception('recommend primary client failed: %s', e)
                # HTTP fallback for recommend as well
                if BASE_URL and API_KEY:
                    try:
                        import httpx
                        url = BASE_URL.rstrip("/") + "/chat/completions"
                        headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
                        body = {
                            "model": model_to_use,
                            "messages": [
                                {"role": "system", "content": "تو یک مشاور حرفه‌ای پوست هستی."},
                                {"role": "user", "content": prompt}
                            ],
                            "temperature": 0.5,
                        }
                        r = httpx.post(url, json=body, headers=headers, timeout=20.0, verify=True, trust_env=False)
                        r.raise_for_status()
                        data = r.json()
                        answer = data.get("choices", [])[0].get("message", {}).get("content", "").strip()
                    except Exception as e2:
                        logger.exception('recommend HTTP fallback (sdk fail path) failed: %s', e2)

        if not answer and BASE_URL and API_KEY:
            try:
                import httpx
                url = BASE_URL.rstrip("/") + "/chat/completions"
                headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
                body = {
                    "model": model_to_use,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.5,
                }
                r = httpx.post(url, json=body, headers=headers, timeout=20.0, verify=True, trust_env=False)
                r.raise_for_status()
                data = r.json()
                answer = data.get("choices", [])[0].get("message", {}).get("content", "").strip()
            except Exception as e:
                logger.exception('recommend HTTP fallback failed: %s', e)

        if not answer:
            # Do NOT fabricate recommendations when LLM is unavailable. Return a graceful service message.
            answer = "متأسفانه سرویس تولید پاسخ موقتاً در دسترس نیست. لطفاً چند لحظه بعد دوباره تلاش کنید."


        recommended_product_ids = [s["id"] for s in summaries] if summaries else []
        log = {
            "priority_used": chosen_priority,
            "recommended_product_ids": recommended_product_ids,
            "recommended_products": [{"id": s["id"], "name": s["name"], "summary_source": s.get("summary_source")} for s in summaries] if summaries else [],
            "user_message": user_message,
            "profile": profile,
            "llm_unavailable": bool(not answer or answer.startswith("متأسفانه سرویس")),
        }
        if llm_agent is not None and user_id:
            try:
                mem = llm_agent.get_conversation_context(user_id, num_messages=2)
                print(f"Memory context for user_id={user_id}: {mem}")
                orig = answer
                stripped = False
                if mem and "سلام" in mem.lower():
                    new_ans = _strip_redundant_greeting(answer)
                    stripped = (new_ans != answer)
                    answer = new_ans
                logger.info(
                    "chat:recommend user_id=%s mem_present=%s stripped=%s user='%s' ans_before='%s' ans_after='%s' prio=%s ids=%s",
                    user_id, bool(mem), stripped, str(user_message)[:80], str(orig)[:120], str(answer)[:120], chosen_priority, [s['id'] for s in summaries] if summaries else []
                )
            except Exception as e:
                logger.exception('postprocess recommend failed: %s', e)
        return answer, log
    except Exception as e:
        logger.exception('recommend failed unexpected: %s', e)
        raise RuntimeError("خطا در recommend: " + str(e)) from e

