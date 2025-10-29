import os
import time
from typing import Optional

from dotenv import load_dotenv, find_dotenv
from openai import OpenAI
import httpx


def build_client() -> OpenAI:
    # Load env from nearest .env if present
    env_file = find_dotenv(usecwd=True)
    if env_file:
        load_dotenv(env_file, override=True)

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    base_url = (os.getenv("OPENAI_BASE_URL") or "").strip()

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Export it or create a .env file.")

    # Avoid system proxies to reduce TLS/proxy issues
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"):
        os.environ.pop(k, None)

    http_client = httpx.Client(trust_env=False, verify=True, timeout=30.0)

    return OpenAI(
        api_key=api_key,
        base_url=base_url.rstrip("/") if base_url else None,
        http_client=http_client,
    )


def test_gpt_simple(prompt: str = "سلام! یه جواب کوتاه بده.", model: Optional[str] = None) -> None:
    client = build_client()
    model_to_use = model or os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini")

    print(f"Using model: {model_to_use}")
    t0 = time.time()
    resp = client.chat.completions.create(
        model=model_to_use,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    dt_ms = int((time.time() - t0) * 1000)

    text = resp.choices[0].message.content.strip()
    print("Status: OK")
    print(f"Latency: {dt_ms} ms")
    print("Response:\n" + text)


if __name__ == "__main__":
    # Example usage: python test_gpt_api.py
    # Or: OPENAI_MODEL=openai/gpt-4o-mini python test_gpt_api.py
    user_prompt = os.getenv("TEST_PROMPT", "سلام! میشه یک جمله انگیزشی کوتاه بگی؟")
    test_gpt_simple(prompt=user_prompt)
