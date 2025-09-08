# 파일: app/chatbot/_smoke.py
import os
from app.chatbot.Agent_Rag_Chatbot import initialize_activities, run_query
from app.services.user_service import load_user_profile

if __name__ == "__main__":
    # 1) 활동 로드 (DB에서)
    initialize_activities()
    print("[OK] activities loaded from DB")

    # 2) 유저 프로필 로드 (기존 JSON 유지)
    user_id = os.getenv("TEST_USER_ID", "tina")
    user_profile = load_user_profile(user_id)
    if not user_profile:
        # 최소 더미 프로필로 테스트
        user_profile = {
            "id": user_id,
            "interests": ["AI", "데이터사이언스"],
            "timetable": [{"day":"월","startTime":"13:00","endTime":"15:00"}]
        }
        print(f"[WARN] user_profile not found -> using dummy profile: {user_profile}")

    # 3) 질의 테스트
    question = os.getenv("TEST_QUESTION", "AI 관련 비교과 추천해줘")
    answer, rec_ids = run_query(user_profile, question)

    print("\n=== ANSWER ===\n", answer)
    print("\n=== RECOMMENDED IDS (internal) ===\n", rec_ids)