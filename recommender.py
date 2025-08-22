import json
import os
from pathlib import Path
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv, find_dotenv

# --- Load ENV (robust) ---
# Try to locate .env relative to this file to avoid CWD issues
BASE_DIR = Path(__file__).resolve().parent
env_file = find_dotenv(usecwd=True) or str(BASE_DIR / ".env")
load_dotenv(env_file, override=True)

API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = os.getenv("OPENAI_BASE_URL")
MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini")

if not API_KEY:
    raise RuntimeError("OPENAI_API_KEY not loaded. Ensure it exists in .env or environment variables.")

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL
)

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
def load_profile(row_index=0):
    df = pd.read_excel("data/shenakht_poosti.xlsx")
    row = df.iloc[row_index].to_dict()
    return row

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
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return resp.choices[0].message.content.strip()

# --- Recommend routine ---
def recommend(profile, user_message):
    products, comments = load_data()
    candidates = products[:3]  # برای تست، فقط ۳ محصول اول

    summaries = []
    for p in candidates:
        s = summarize_comments(p["id"], comments)
        summaries.append({"id": p["id"], "name": p["nameFa"], "summary": s})

    prompt = f"""
    پروفایل کاربر:
    {json.dumps(profile, ensure_ascii=False)}

    پیام کاربر:
    {user_message}

    محصولات کاندید:
    {json.dumps(summaries, ensure_ascii=False)}

    -----
    لطفاً یک روتین پوستی پیشنهاد بده و از همین محصولات انتخاب کن.
    توضیح بده چرا این محصولات مناسب‌اند.
    """
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "تو یک مشاور حرفه‌ای پوست هستی."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )
    return resp.choices[0].message.content.strip()
