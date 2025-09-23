from typing import Dict, Any

def build_user_message_payload(user_id: str, message: str, chat_id: str | None = None) -> Dict[str, Any]:
    return {"user_id": user_id, "chat_id": chat_id, "message": message}


