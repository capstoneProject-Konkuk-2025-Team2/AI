def build_user_context(user_profile: dict) -> str:
    parts = []

    name = user_profile.get("이름", "알 수 없음")
    major = user_profile.get("학과", "")
    year = user_profile.get("학년", "")
    interests = user_profile.get("관심사", [])
    timetable = user_profile.get("시간표", [])

    if name or major or year:
        parts.append(f"{name}은(는) {major} {year}입니다.")
    if interests:
        parts.append(f"관심사는 {', '.join(interests)}입니다.")
    if timetable:
        schedule_str = "; ".join(
            [f"{item['요일']} {item['시작시간']}~{item['종료시간']}" for item in timetable]
        )
        parts.append(f"수업 시간은 다음과 같습니다: {schedule_str}.")
    return " ".join(parts)
