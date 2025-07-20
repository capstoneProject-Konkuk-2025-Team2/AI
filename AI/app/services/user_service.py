import os
import json

USER_TABLE_PATH = "app/data/users.json"

def save_user_profile(profile_data: dict):
    user_id = str(profile_data["id"])
    users = {}

    if os.path.exists(USER_TABLE_PATH):
        with open(USER_TABLE_PATH, "r", encoding="utf-8") as f:
            try:
                users = json.load(f)
            except json.JSONDecodeError:
                users = {}

    users[user_id] = profile_data

    with open(USER_TABLE_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def load_user_profile(user_id: str) -> dict | None:
    if not os.path.exists(USER_TABLE_PATH):
        return None
    try:
        with open(USER_TABLE_PATH, "r", encoding="utf-8") as f:
            users = json.load(f)
        return users.get(str(user_id))
    except Exception:
        return None
