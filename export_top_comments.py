import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

DATA_DIR = Path(__file__).resolve().parent / "data"
PRODUCTS_PATH = DATA_DIR / "products.json"
COMMENTS_PATH = DATA_DIR / "comments.json"

# Use existing configured OpenAI client and model from recommender
from recommender import client as _ai_client, MODEL as _AI_MODEL


def _load_products_and_comments() -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    with open(PRODUCTS_PATH, encoding="utf-8") as f:
        prod_raw = json.load(f)
        products = prod_raw[2]["data"]
    with open(COMMENTS_PATH, encoding="utf-8") as f:
        comm_raw = json.load(f)
        comments = comm_raw[2]["data"]
    return products, comments


def _product_name(p: Dict[str, Any]) -> str:
    return p.get("nameFa") or p.get("nameEn") or p.get("name") or ""


def _classify_sentiment_batch(texts: List[str]) -> List[str]:
    """Classify a list of comment texts into 'pos' | 'neg' | 'neu' using the LLM.
    Returns one label per input text in order."""
    if not texts:
        return []
    # Truncate each text to keep tokens in check
    trunc = [t.strip().replace("\n", " ")[:500] for t in texts]
    prompt = (
        "متن‌های زیر نظرات کاربران هستند. برای هر نظر فقط یکی از برچسب‌های زیر را بده:\n"
        "- pos (مثبت)\n- neg (منفی)\n- neu (خنثی)\n\n"
        "خروجی باید دقیقا یک آرایه JSON از رشته‌ها با همین ترتیب ورودی باشد، مثلا: [\"pos\",\"neg\",...]\n"
        "هیچ متن اضافه ننویس.\n\n"
        "نظرات:\n" + "\n".join([f"- {i+1}) {t}" for i, t in enumerate(trunc)])
    )
    try:
        resp = _ai_client.chat.completions.create(
            model=_AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        content = resp.choices[0].message.content.strip()
        # Sanitize possible code fences or extra text
        s = content
        if s.startswith("```"):
            s = s.lstrip("`")
            if "\n" in s:
                s = s.split("\n", 1)[1]
            s = s.strip()
            if s.endswith("```"):
                s = s[: -3].strip()
        if not (s.startswith("[") and s.rstrip().endswith("]")):
            start = s.find("[")
            end = s.rfind("]")
            if start != -1 and end != -1 and end > start:
                s = s[start : end + 1]
        labels = json.loads(s)
        if isinstance(labels, list) and all(isinstance(x, str) for x in labels):
            return labels[: len(texts)] + ["neu"] * max(0, len(texts) - len(labels))
    except Exception as e:
        print(f"LLM sentiment batch failed: {e}")
    # Fallback neutral if LLM fails
    return ["neu"] * len(texts)


def build_top_comments_json(max_per_side: int = 10, limit_products: int | None = None) -> Dict[str, Any]:
    products, comments = _load_products_and_comments()

    # group comments by product_id
    prod_to_comments: Dict[str, List[Dict[str, Any]]] = {}
    for c in comments:
        pid = str(c.get("product_id"))
        if not pid:
            continue
        prod_to_comments.setdefault(pid, []).append(c)

    items: List[Dict[str, Any]] = []
    for p in products:
        pid = str(p.get("id"))
        name = _product_name(p)
        clist = prod_to_comments.get(pid, [])
        if not clist:
            continue
        # Prepare texts and classify in manageable batches
        texts = [str(c.get("description") or "").strip() for c in clist if c.get("description")]
        labels: List[str] = []
        B = 25
        for i in range(0, len(texts), B):
            labels.extend(_classify_sentiment_batch(texts[i : i + B]))
        pos_list: List[str] = []
        neg_list: List[str] = []
        for t, lb in zip(texts, labels):
            if lb == "pos" and len(pos_list) < max_per_side:
                pos_list.append(t)
            elif lb == "neg" and len(neg_list) < max_per_side:
                neg_list.append(t)
            if len(pos_list) >= max_per_side and len(neg_list) >= max_per_side:
                break
        item = {
            "id": pid,
            "name": name,
            "num_comments": len(clist),
            "positive_comments": pos_list,
            "negative_comments": neg_list,
        }
        items.append(item)

    # sort products by number of comments desc
    items.sort(key=lambda x: x["num_comments"], reverse=True)
    if limit_products is not None and limit_products > 0:
        items = items[:limit_products]

    out = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "model": _AI_MODEL,
        "max_per_side": max_per_side,
        "products": items,
    }
    return out


def main():
    parser = argparse.ArgumentParser(description="Export top positive/negative comments per product to JSON (LLM-based)")
    parser.add_argument("--out", default=str(DATA_DIR / "top_comments.json"), help="Output JSON path")
    parser.add_argument("--max-per-side", type=int, default=10, help="Max positive/negative comments per product")
    parser.add_argument("--limit-products", type=int, default=0, help="Limit number of products (0 for all)")
    args = parser.parse_args()

    result = build_top_comments_json(max_per_side=args.max_per_side, limit_products=(args.limit_products or None))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, sort_keys=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
