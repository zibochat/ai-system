import requests
import time
import random
from typing import Optional
from config import GEMINI_API_KEY, GEMINI_MODEL


def _normalize_model_name(name: str) -> str:
    return name if name.startswith("models/") else f"models/{name}"


def generate_text(
    prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    system_instruction: Optional[str] = None,
    retries: int = 5,
    timeout: int = 60,
) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set. Set env or edit config.py")
    model_path = _normalize_model_name(GEMINI_MODEL)
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}] 
            }
        ],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "candidateCount": 1,
            "responseMimeType": "text/plain"
        }
    }
    if system_instruction:
        payload["systemInstruction"] = {"role": "system", "parts": [{"text": system_instruction}]}

    attempt = 0
    while True:
        attempt += 1
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.ProxyError) as e:
            if attempt <= retries:
                # exponential backoff with jitter
                delay = min(10, (2 ** (attempt - 1))) + random.uniform(0, 0.5)
                time.sleep(delay)
                continue
            raise RuntimeError(f"Gemini network error after {attempt-1} retries: {e}") from e

        if resp.status_code == 404:
            raise RuntimeError(
                f"Model not found (404). Check GEMINI_MODEL='{GEMINI_MODEL}' and key access."
            )

        # Retry on transient server-side errors
        if resp.status_code in (429, 500, 502, 503, 504):
            if attempt <= retries:
                # shrink max tokens on retries to reduce load
                payload["generationConfig"]["maxOutputTokens"] = max(256, int(payload["generationConfig"].get("maxOutputTokens", max_tokens) * 0.8))
                delay = min(12, (2 ** (attempt - 1))) + random.uniform(0, 0.7)
                time.sleep(delay)
                continue
            try:
                err = resp.json()
            except Exception:
                err = {"error": resp.text}
            raise RuntimeError(f"Gemini API error {resp.status_code}: {err}")

        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            try:
                err = resp.json()
            except Exception:
                err = {"error": resp.text}
            raise RuntimeError(f"Gemini API error {resp.status_code}: {err}") from e
        break

    data = resp.json()
    fb = data.get("promptFeedback") or {}
    br = fb.get("blockReason")
    if br and br != "BLOCK_NONE":
        return f"پاسخ توسط سامانه مسدود شد: {br}"
    candidates = data.get("candidates") or []
    if not candidates:
        # include any debug info if available
        debug = fb or {}
        return f"پاسخی دریافت نشد: {debug}" if debug else "پاسخی دریافت نشد"
    first = candidates[0] or {}
    content = first.get("content") or {}
    parts = content.get("parts") or []
    if parts and isinstance(parts[0], dict):
        return parts[0].get("text", "پاسخی دریافت نشد")
    return "پاسخی دریافت نشد"
