import os
import json
from pathlib import Path
from typing import Any, List, Dict, Optional


def _langchain_available() -> bool:
    try:
        import langchain.chat_models  # type: ignore
        import langchain.embeddings  # type: ignore
        import langchain.vectorstores  # type: ignore
        import langchain.schema  # type: ignore
        return True
    except Exception:
        return False


BASE_FAISS_DIR = Path("data/faiss")
BASE_FAISS_DIR.mkdir(parents=True, exist_ok=True)


def _user_dir(user_id: str) -> Path:
    return BASE_FAISS_DIR / str(user_id)


def _meta_path(user_id: str) -> Path:
    return _user_dir(user_id) / "meta.json"


def _ensure_user_dir(user_id: str):
    d = _user_dir(user_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_meta(user_id: str) -> Dict[str, Dict[str, Any]]:
    p = _meta_path(user_id)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_meta(user_id: str, meta: Dict[str, Dict[str, Any]]):
    p = _meta_path(user_id)
    _ensure_user_dir(user_id)
    p.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_embedder(embeddings_model: Optional[str] = None):
    if not _langchain_available():
        raise RuntimeError("LangChain/embeddings not available; install requirements to use FAISS helpers")
    # dynamic imports
    from langchain.embeddings import HuggingFaceEmbeddings, OpenAIEmbeddings
    # prefer explicit model, else try a lightweight HF then fallback to OpenAI
    if embeddings_model:
        return HuggingFaceEmbeddings(model_name=embeddings_model)
    try:
        return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    except Exception:
        return OpenAIEmbeddings()


def upsert_user_docs(user_id: str, docs: List[Dict[str, Any]], embeddings_model: Optional[str] = None) -> None:
    """Upsert docs (each: {id, text, meta}) into a per-user FAISS index (persisted).
    This rebuilds the index from combined meta for simplicity and persists it.
    """
    if not _langchain_available():
        raise RuntimeError("LangChain not available; install langchain and faiss-cpu to enable upsert_user_docs")
    meta = _load_meta(user_id)
    # update/insert docs by id
    for d in docs:
        if "id" not in d or "text" not in d:
            raise ValueError("each doc must have 'id' and 'text'")
        meta[d["id"]] = {"text": d["text"], "meta": d.get("meta", {})}

    # rebuild index from all texts
    texts = [v["text"] for v in meta.values()]
    metadatas = [v["meta"] for v in meta.values()]
    embedder = _build_embedder(embeddings_model)
    try:
        from langchain.vectorstores import FAISS
        store = FAISS.from_texts(texts, embedder, metadatas=metadatas)
    except Exception as e:
        raise RuntimeError(f"failed to build FAISS store: {e}") from e

    d = _ensure_user_dir(user_id)
    # persist store + meta
    try:
        store.save_local(str(d))
        _save_meta(user_id, meta)
    except Exception as e:
        raise RuntimeError(f"failed to save FAISS store: {e}") from e


def load_user_index(user_id: str, embeddings_model: Optional[str] = None):
    if not _langchain_available():
        return None
    d = _user_dir(user_id)
    if not d.exists():
        return None
    embedder = _build_embedder(embeddings_model)
    try:
        from langchain.vectorstores import FAISS
        # The FAISS loader may deserialize pickle files. These indexes were created locally by this application,
        # so allow dangerous deserialization for trusted local data so loading succeeds. Ensure files are trusted.
        store = FAISS.load_local(str(d), embedder, allow_dangerous_deserialization=True)
        return store
    except Exception as e:
        # surface full traceback to a logfile for diagnosis instead of silently returning None
        try:
            import traceback
            logdir = Path("logs")
            logdir.mkdir(parents=True, exist_ok=True)
            with open(logdir / "zibochat_faiss_load_error.log", "a", encoding="utf-8") as f:
                f.write("--- FAISS load error for user_id=%s ---\n" % user_id)
                traceback.print_exc(file=f)
                f.write("\n")
        except Exception:
            pass
        # re-raise so callers and tests see the underlying error
        raise


def retrieve_user_memory(user_id: str, query: str, k: int = 6, embeddings_model: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return list of {'text','meta','score'} from user's FAISS index."""
    if not _langchain_available():
        return []
    store = load_user_index(user_id, embeddings_model=embeddings_model)
    if store is None:
        return []
    try:
        results = store.similarity_search_with_score(query, k=k)
        out = []
        for doc, score in results:
            out.append({"text": doc.page_content, "meta": getattr(doc, "metadata", {}), "score": float(score)})
        return out
    except Exception:
        return []


def ensure_product_summary_cached(user_id: str, product_id: str, summary_text: Optional[str] = None, model: Optional[str] = None, client: Optional[Any] = None) -> Dict[str, Any]:
    """Ensure product summary for product_id exists in user's index. If summary_text provided uses it, otherwise will call LLM to summarize via chat_with_context.
    Returns the stored doc meta.
    """
    meta = _load_meta(user_id)
    # check existing
    for doc_id, doc in meta.items():
        m = doc.get("meta", {})
        if m.get("type") == "product_summary" and m.get("product_id") == str(product_id):
            return {"id": doc_id, "meta": m}

    # need to create
    if summary_text is None:
        if client is None:
            raise RuntimeError("No summary_text and no client to call LLM")
        # ask model to summarize; build simple prompt
        prompt = f"خلاصه‌ای کوتاه از نظرات و مشخصات محصول با id={product_id}:\n" + "(متن نظرات یا توضیحات)"
        resp = chat_with_context(messages=[{"role": "user", "content": prompt}], model=model or os.getenv("OPENAI_MODEL"), user_id=user_id, client=client)
        summary_text = resp

    doc_id = f"product_summary_{product_id}"
    doc = {"id": doc_id, "text": summary_text, "meta": {"type": "product_summary", "product_id": str(product_id), "created_at": __import__("datetime").datetime.utcnow().isoformat()}}
    upsert_user_docs(user_id, [doc])
    return {"id": doc_id, "meta": doc["meta"]}


def extract_and_store_chat_facts(user_id: str, chat_text: str, model: Optional[str] = None, client: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Ask the model to extract key facts (likes, preferences, sensitivities) as JSON and store them as chat_fact docs.
    Returns list of stored doc metas.
    """
    # Simple instruct to output JSON array of {key, value}
    prompt = (
        "لطفاً از متن زیر حقایق کوتاه و قابل ذخیره‌سازی استخراج کن به صورت JSON آرایه‌ای از آبجکت‌ها با فیلدهای: key, value. "
        "(مثلاً 'likes','dislikes','sensitivity','personality')\n\n" + chat_text
    )
    resp = chat_with_context(messages=[{"role": "user", "content": prompt}], model=model or os.getenv("OPENAI_MODEL"), user_id=user_id, client=client)
    # try parse JSON from response
    facts = []
    try:
        parsed = json.loads(resp)
        if isinstance(parsed, list):
            for i, f in enumerate(parsed):
                key = f.get("key") or f.get("k") or f.get("name")
                val = f.get("value") or f.get("v") or f.get("val")
                if key and val:
                    doc_id = f"chatfact_{int(__import__('time').time())}_{i}"
                    docs = [{"id": doc_id, "text": f"{key}: {val}", "meta": {"type": "chat_fact", "key": key}}]
                    upsert_user_docs(user_id, docs)
                    facts.append({"id": doc_id, "key": key, "value": val})
    except Exception:
        # best-effort: fallback to store full chat_text as a single fact
        doc_id = f"chat_snippet_{int(__import__('time').time())}"
        docs = [{"id": doc_id, "text": chat_text[:2000], "meta": {"type": "conversation_snippet"}}]
        upsert_user_docs(user_id, docs)
        facts.append({"id": doc_id, "type": "conversation_snippet"})
    return facts


def _normalize_messages(messages: List[Dict[str, Any]]):
    out = []
    if _langchain_available():
        from langchain.schema import HumanMessage, SystemMessage, AIMessage
        for m in messages:
            if isinstance(m, dict):
                role = m.get("role")
                c = m.get("content")
                if role == "system":
                    out.append(SystemMessage(content=c))
                elif role == "assistant":
                    out.append(AIMessage(content=c))
                else:
                    out.append(HumanMessage(content=c))
            else:
                out.append(m)
    else:
        # return messages as-is for the OpenAI client fallback
        for m in messages:
            out.append(m)
    return out


def chat_with_context(messages: List[Dict[str, Any]], model: Optional[str] = None, user_id: Optional[str] = None, temperature: float = 0.5, client: Optional[Any] = None) -> str:
    """Unified chat helper. messages is a list of {'role','content'} dicts (or langchain message objects).
    If user_id is provided, top-k memories are retrieved and prepended as a system message.
    If LangChain is available, uses ChatOpenAI; otherwise falls back to the provided openai client.
    """
    model_to_use = model or os.getenv("OPENAI_MODEL")

    # validate model against the server-supported list when we have a client
    def _validate_model_for_client(client_obj, preferred: str | None) -> Optional[str]:
        if client_obj is None or preferred is None:
            return preferred
        try:
            # get available models from the server
            models = client_obj.models.list()
            avail = [getattr(m, "id", None) for m in getattr(models, "data", [])]
            avail = [a for a in avail if a]
            # exact match
            if preferred in avail:
                return preferred
            # try matching by suffix (model name without provider prefix)
            pref_name = preferred.split('/')[-1]
            for a in avail:
                if a.split('/')[-1] == pref_name:
                    return a
            # try a small prioritized fallback list
            preferred_fallbacks = [
                "openai/gpt-4o-mini",
                "openai/gpt-4.1",
                "openai/gpt-4.1-mini",
                "openai/gpt-5-mini",
                "openai/gpt-5-chat",
            ]
            for cand in preferred_fallbacks:
                if cand in avail:
                    return cand
            # otherwise return first available model
            if avail:
                return avail[0]
        except Exception:
            # if listing models fails, don't block; return the preferred
            return preferred
        return preferred

    if client is not None:
        model_to_use = _validate_model_for_client(client, model_to_use)

    # if user memory exists, retrieve and prepend
    if user_id and _langchain_available():
        mem = retrieve_user_memory(user_id, " ", k=6)  # fallback query: return important docs
        if mem:
            mem_texts = "\n".join([f"- {m['meta'].get('type','')}: {m['text'][:200]}" for m in mem])
            sys = {"role": "system", "content": f"User memory (most relevant):\n{mem_texts}"}
            messages = [sys] + messages
    # Use LangChain if available
    if _langchain_available():
        try:
            from langchain.chat_models import ChatOpenAI
            llm = ChatOpenAI(temperature=temperature, model_name=model_to_use)
            lc_msgs = _normalize_messages(messages)
            resp = llm(lc_msgs)
            # ChatOpenAI returns a ChatResult; try to extract text
            if hasattr(resp, "generations"):
                try:
                    return resp.generations[0][0].text
                except Exception:
                    return str(resp)
            if hasattr(resp, "content"):
                return resp.content
            return str(resp)
        except Exception as e:
            # fallback to client
            if client is None:
                raise RuntimeError(f"Chat via LangChain failed: {e}") from e

    # fallback to OpenAI-like client
    if client is None:
        raise RuntimeError("No client provided for chat fallback and LangChain not available")
    try:
        resp = client.chat.completions.create(
            model=model_to_use,
            messages=[{"role": m.get("role"), "content": m.get("content")} for m in messages],
            temperature=temperature,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        # Attempt a direct HTTP fallback using httpx when the OpenAI SDK fails (network/proxy issues)
        try:
            import httpx
            # read sanitized envs (may be set by recommender)
            base = os.getenv("OPENAI_BASE_URL")
            api_key = os.getenv("OPENAI_API_KEY")
            if not base or not api_key:
                raise RuntimeError("Fallback unavailable: OPENAI_BASE_URL or OPENAI_API_KEY not set in environment")
            url = base.rstrip("/") + "/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": model_to_use,
                "messages": [{"role": m.get("role"), "content": m.get("content")} for m in messages],
                "temperature": temperature,
            }
            # avoid using environment proxies
            with httpx.Client(trust_env=False, verify=True, timeout=30) as c:
                r = c.post(url, json=payload, headers=headers)
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP fallback failed: {r.status_code} {r.text}")
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e2:
            # surface both errors for debugging
            raise RuntimeError(f"chat failed: sdk_error={e} ; fallback_error={e2}") from e2
