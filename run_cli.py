import sys
import json
from profile_loader import load_profile_from_excel
from gemini_client import generate_text
from retriever import (
    load_products_json,
    load_comments_json,
    load_summaries_json,
    build_corpus,
    build_corpus_from_summaries,
    make_tfidf_retriever,
    retrieve_top_k,
)

SYSTEM_INSTRUCTION = (
    "تو یک دستیار مراقبت از پوست هستی. پاسخ را کوتاه، فارسی و مبتنی بر شواهد بده."
)

PROMPT_TEMPLATE = (
    "با توجه به پروفایل کاربر و اسنیپت‌ها، 3 محصول مناسب پیشنهاد بده.\n"
    "برای هر محصول: نام، 1-2 دلیل مستند به اسنیپت‌ها، و 1-2 نقل‌قول کوتاه از کامنت‌ها.\n"
    "اولویت با اسنیپت‌هاست؛ اگر شواهد کافی نبود، یک توصیه عمومی کوتاه و امن بده و اعلام کن که از دانش عمومی استفاده شده.\n\n"
    "پروفایل کاربر (JSON):\n{profile}\n\n"
    "اسنیپت‌های کاندید:\n{snippets}\n\n"
    "سوال: {question}\n"
)


def main():
    # Ensure UTF-8 output for Persian
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    
    profile = load_profile_from_excel()
    # Prefer precomputed summaries if available
    summaries = load_summaries_json("data/summaries.json")
    if summaries is not None and not summaries.empty:
        texts, metas = build_corpus_from_summaries(summaries, max_quotes=2)
    else:
        products = load_products_json("data/products.json")
        comments = load_comments_json("data/comments.json")
        texts, metas = build_corpus(products, comments, max_comments_per_product=5)

    if not texts:
        print("هیچ متنی برای بازیابی پیدا نشد (محصول یا کامنت خالی است).")
        return
    
    vectorizer, X = make_tfidf_retriever(texts)

    print("پروفایل کاربر:")
    print(json.dumps(profile, ensure_ascii=False, indent=2))

    print("\nسوالت رو بپرس (Ctrl+C برای خروج):")
    try:
        while True:
            try:
                q = input("user> ")
            except EOFError:
                print("\nخروج")
                break
            query = json.dumps(profile, ensure_ascii=False) + "\n" + q
            top = retrieve_top_k(query, vectorizer, X, texts, metas, k=7)
            # compress snippets to avoid token overflow
            snippets = []
            for item in top:
                t = item["text"]
                if len(t) > 700:
                    t = t[:700]
                name = item["meta"].get("nameFa", "")
                snippets.append(f"- {name}:\n{t}")
            snippets_text = "\n\n".join(snippets)

            full_prompt = PROMPT_TEMPLATE.format(
                profile=json.dumps(profile, ensure_ascii=False),
                snippets=snippets_text,
                question=q,
            )
            try:
                answer = generate_text(full_prompt, system_instruction=SYSTEM_INSTRUCTION)
                if not answer or answer.strip().startswith("پاسخی دریافت نشد"):
                    # second try with lower temperature (no greeting fallback)
                    answer = generate_text(full_prompt, temperature=0.0, system_instruction=SYSTEM_INSTRUCTION)
            except Exception as e:
                answer = f"خطا در ارتباط با Gemini: {e}"
            print("assistant>")
            print(answer)
    except KeyboardInterrupt:
        print("\nخروج")


if __name__ == "__main__":
    main()
