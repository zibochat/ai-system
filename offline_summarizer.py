import json
from typing import List, Dict, Any
from pathlib import Path

from retriever import load_products_json, load_comments_json
from gemini_client import generate_text

SYSTEM_INSTRUCTION = (
    "تو یک دستیار مراقبت از پوست هستی. خلاصهٔ دقیق، کوتاه و مبتنی بر شواهد بنویس."
)
def _chunk_list(items: List[str], chunk_size: int) -> List[List[str]]:
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]
def summarize_comments(product: Dict[str, Any], comments: List[str]) -> Dict[str, Any]:
    name_fa = str(product.get("nameFa") or "")
    pid = str(product.get("id") or "")
    desc = str(product.get("description") or "")

    chunks = _chunk_list([c for c in comments if isinstance(c, str) and c.strip()], 20)
    partials: List[str] = []
    for chunk in chunks:
        prompt = (
            "خلاصه کن: نکات کلیدی زیر را از این نظرات استخراج کن به صورت بولت کوتاه فارسی.\n"
            "- مناسب برای چه نوع پوست/مشکلات (مثلاً چرب/مختلط/آکنه)\n"
            "- مزایا/معایب پرتکرار (۲-۴ مورد)\n"
            "- عوارض یا شکایت‌های پرتکرار (۱-۳ مورد)\n"
            "- ۱ تا ۲ نقل‌قول خیلی کوتاه (<= 100 کاراکتر)\n\n"
            f"محصول: {name_fa} | id={pid}\nتوضیح: {desc}\n"
            f"نظرات:\n- " + "\n- ".join(chunk)
        )
        txt = generate_text(prompt, system_instruction=SYSTEM_INSTRUCTION)
        partials.append(txt or "")

    reduce_prompt = (
        "خلاصه نهایی و فشردهٔ زیر را بساز. فارسی روان و کوتاه، بدون اغراق.\n"
        "ساختار خروجی:\n"
        "- مناسب برای: <نوع پوست/مسائل>\n"
        "- مزایا: <۲-۴ بولت کوتاه>\n"
        "- معایب/هشدار: <۱-۳ بولت کوتاه>\n"
        "- نقل‌قول‌ها: <۱-۲ نقل‌قول بسیار کوتاه>\n\n"
        f"خلاصه‌های جزئی:\n{ '\n---\n'.join(partials) }\n"
    )
    final_summary = generate_text(reduce_prompt, system_instruction=SYSTEM_INSTRUCTION)

    quotes_prompt = (
        "از متن زیر ۱ تا ۲ نقل‌قول خیلی کوتاه فارسی (<=100 کاراکتر) که نمایندهٔ تجربهٔ کاربران باشد جدا کن.\n"
        "فقط نقل‌قول‌ها را هرکدام در یک خط بده.\n\n"
        + "\n---\n".join(partials)
    )
    quotes_raw = generate_text(quotes_prompt, temperature=0.0, system_instruction=SYSTEM_INSTRUCTION) or ""
    quotes = [q.strip("- \n") for q in quotes_raw.splitlines() if q.strip()][:2]

    return {
        "product_id": pid,
        "nameFa": name_fa,
        "summary": final_summary or "",
        "quotes": quotes,
    }

def build_summaries(output_path: str = "data/summaries.json", max_comments_per_product: int = 120) -> str:
    products_df = load_products_json("data/products.json")
    comments_df = load_comments_json("data/comments.json")

    if products_df.empty or comments_df.empty:
        raise RuntimeError("محصول یا کامنت خالی است؛ فایل‌های JSON را بررسی کنید.")


    grouped = comments_df.groupby("product_id", as_index=False).agg({"description": list})
    comment_map = {
        str(r.product_id): [c for c in (r.description or []) if isinstance(c, str) and c.strip()][:max_comments_per_product]
        for _, r in grouped.iterrows()
    }

    out: List[Dict[str, Any]] = []
    for _, pr in products_df.iterrows():
        pid = str(pr.get("id", ""))
        cmts = comment_map.get(pid) or []
        if not cmts:
            continue
        out.append(summarize_comments(pr, cmts))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return output_path

if __name__ == "__main__":
    path = build_summaries()
    print(f"Saved summaries to: {path}")
