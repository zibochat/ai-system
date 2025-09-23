import os
import sys
import readline  # optional for nicer CLI input history
from pathlib import Path

from recommender import recommend, load_profile

try:
    import llm_agent
except Exception:
    llm_agent = None

# Local greeting-stripper (same logic as UI)
import re as _re

def _strip_greeting_ui(text: str) -> str:
    if not isinstance(text, str):
        return text
    t = text.lstrip()
    patterns = [
        r'^(سلام( و وقت بخیر)?)\b[\s\W_]*',
        r'^(درود)\b[\s\W_]*',
        r'^(hi|hello|hey)\b[\s\W_]*',
    ]
    for pat in patterns:
        new_t = _re.sub(pat, '', t, flags=_re.IGNORECASE)
        if new_t != t:
            t = new_t
            break
    return t


def main():
    import argparse
    parser = argparse.ArgumentParser(description="ZiboChat CLI runner")
    parser.add_argument('--user-id', default=os.getenv('ZIBO_USER_ID', 'testuser'))
    parser.add_argument('--profile-row', type=int, default=0, help='Row index from shenakht_poosti.xlsx to use as profile')
    args = parser.parse_args()

    # Load a sample profile (like streamlit auto-load)
    try:
        profile = load_profile(args.profile_row)
    except Exception:
        profile = {}

    print(f"[ZiboChat CLI] user_id={args.user_id} | profile_row={args.profile_row}")
    print("Type 'exit' or Ctrl+C to quit.\n")

    while True:
        try:
            user_input = input('you> ').strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye.")
            break
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", ":q", "\x04"}:
            print("bye.")
            break

        try:
            answer, log = recommend(profile, user_input, max_count=5, user_id=args.user_id)
            answer = _strip_greeting_ui(answer)
            print("bot>", answer)
            # persist memory
            if llm_agent is not None:
                try:
                    llm_agent.save_conversation_interaction(args.user_id, user_input, answer)
                except Exception:
                    pass
        except Exception as e:
            print("bot> error:", e)


if __name__ == '__main__':
    main()
