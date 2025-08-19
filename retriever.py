import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Tuple
import json
from pathlib import Path


def _load_phpmyadmin_table_json(path: str, table_name: str) -> List[Dict]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict) and entry.get("type") == "table" and entry.get("name") == table_name:
                return entry.get("data", []) or []
        # Or maybe file is directly a list of records
        if data and isinstance(data[0], dict) and ("id" in data[0] or "product_id" in data[0]):
            return data
    # Unknown structure
    return []


def load_products_json(path: str = "products.json") -> pd.DataFrame:
    records = _load_phpmyadmin_table_json(path, table_name="products")
    df = pd.DataFrame(records)
    for col in ["id", "nameFa", "nameEn", "description"]:
        if col not in df.columns:
            df[col] = ""
    if not df.empty:
        df["id"] = df["id"].astype(str)
    return df


def load_comments_json(path: str = "comments.json") -> pd.DataFrame:
    records = _load_phpmyadmin_table_json(path, table_name="comments")
    df = pd.DataFrame(records)
    for col in ["id", "product_id", "user_name", "description"]:
        if col not in df.columns:
            df[col] = ""
    if not df.empty:
        df["product_id"] = df["product_id"].astype(str)
    return df


def load_summaries_json(path: str = "data/summaries.json") -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    df = pd.DataFrame(data or [])
    # Expected keys: product_id, nameFa, summary, quotes
    for col in ["product_id", "nameFa", "summary", "quotes"]:
        if col not in df.columns:
            df[col] = "" if col != "quotes" else []
    if not df.empty:
        df["product_id"] = df["product_id"].astype(str)
    return df


# CSV loaders removed (we standardize on JSON/summaries)


def build_corpus(products: pd.DataFrame, comments: pd.DataFrame, max_comments_per_product: int = 5) -> Tuple[List[str], List[Dict]]:
    texts: List[str] = []
    metas: List[Dict] = []

    # Ensure required columns exist
    for col in ["product_id", "description"]:
        if col not in comments.columns:
            comments[col] = ""

    grouped = comments.groupby("product_id", as_index=False).agg({"description": list})
    comment_map = {str(row.product_id): [c for c in (row.description or []) if isinstance(c, str) and c.strip()] for _, row in grouped.iterrows()}

    # If products is empty, synthesize entries from comments only
    if products is None or products.empty:
        for pid, cmts_all in comment_map.items():
            cmts = cmts_all[:max_comments_per_product]
            if not cmts:
                continue
            cmts_joined = " \n".join(cmts)
            text = f"PRODUCT: id={pid}\nCOMMENTS:\n{cmts_joined}"
            texts.append(text)
            metas.append({"id": pid, "nameFa": ""})
        return texts, metas

    # Otherwise, build using products + their comments
    for _, r in products.iterrows():
        pid = str(r.get("id", ""))
        name_fa = str(r.get("nameFa", "") or "")
        name_en = str(r.get("nameEn", "") or "")
        desc = str(r.get("description", "") or "")
        cmts = (comment_map.get(pid) or [])[:max_comments_per_product]
        cmts_joined = " \n".join(cmts)
        text = f"PRODUCT: {name_fa} | {name_en} | id={pid}\nDESC: {desc}\nCOMMENTS:\n{cmts_joined}"
        texts.append(text)
        metas.append({"id": pid, "nameFa": name_fa})
    return texts, metas


def build_corpus_from_summaries(summaries: pd.DataFrame, max_quotes: int = 2) -> Tuple[List[str], List[Dict]]:
    texts: List[str] = []
    metas: List[Dict] = []
    if summaries is None or summaries.empty:
        return texts, metas
    for _, r in summaries.iterrows():
        pid = str(r.get("product_id", ""))
        name_fa = str(r.get("nameFa", "") or "")
        summary = str(r.get("summary", "") or "")
        quotes = r.get("quotes", []) or []
        if isinstance(quotes, str):
            # in case it's a serialized string
            try:
                q = json.loads(quotes)
                if isinstance(q, list):
                    quotes = q
            except Exception:
                quotes = [quotes]
        quotes = [q for q in quotes if isinstance(q, str) and q.strip()][:max_quotes]
        qtext = "\n- ".join(quotes)
        text = f"PRODUCT: {name_fa} | id={pid}\nSUMMARY:\n{summary}\nQUOTES:\n- {qtext}" if qtext else f"PRODUCT: {name_fa} | id={pid}\nSUMMARY:\n{summary}"
        texts.append(text)
        metas.append({"id": pid, "nameFa": name_fa})
    return texts, metas


def make_tfidf_retriever(texts: List[str]):
    vectorizer = TfidfVectorizer(max_features=40000, ngram_range=(1, 2))
    X = vectorizer.fit_transform(texts)
    return vectorizer, X


def retrieve_top_k(query: str, vectorizer: TfidfVectorizer, X, texts: List[str], metas: List[Dict], k: int = 5):
    qv = vectorizer.transform([query])
    sims = cosine_similarity(qv, X)[0]
    idxs = sims.argsort()[::-1][:k]
    results = []
    for i in idxs:
        results.append({
            "meta": metas[i],
            "text": texts[i],
            "score": float(sims[i])
        })
    return results
