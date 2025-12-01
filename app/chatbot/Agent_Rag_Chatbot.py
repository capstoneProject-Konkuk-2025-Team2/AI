import os, re, pickle, hashlib, unicodedata
from pathlib import Path
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime, timedelta   
import faiss

from sqlalchemy import text as sql_text
from app.config.llm_config import client
from app.utils.db import engine

# -----------------------------
# 캐시 및 저장 설정
# -----------------------------
CACHE_DIR = Path(os.getenv("CACHE_DIR", "app/.cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
FAISS_INDEX_FILE = CACHE_DIR / "chunk_faiss.index"
CHUNK_META_FILE = CACHE_DIR / "chunk_meta.pkl"
EMBED_MODEL = "text-embedding-3-small"
EMBED_CACHE_FILE = CACHE_DIR / "embeddings.pkl"

## 임베딩 "디스크 캐시 + 배치 호출"

def _load_embed_cache():
    if EMBED_CACHE_FILE.exists():
        try:
            with open(EMBED_CACHE_FILE, "rb") as f:
                return pickle.load(f)
        except Exception:
            return {}
    return {}

def _save_embed_cache(cache):
    try:
        with open(EMBED_CACHE_FILE, "wb") as f:
            pickle.dump(cache, f)
    except Exception:
        pass

# 전역 1회 로드
_embed_cache = _load_embed_cache()

def get_embedding(text: str) -> np.ndarray:
    key = hashlib.md5((text + "|" + EMBED_MODEL).encode("utf-8")).hexdigest()
    # 메모리 + 디스크 캐시
    if key in _embed_cache:
        return _embed_cache[key]
    local_cache = getattr(get_embedding, "_cache", {})
    if key in local_cache:
        return local_cache[key]

    res = client.embeddings.create(input=[text], model=EMBED_MODEL)
    vec = np.array(res.data[0].embedding, dtype="float32").reshape(1, -1)

    local_cache[key] = vec
    get_embedding._cache = local_cache
    _embed_cache[key] = vec
    _save_embed_cache(_embed_cache)
    return vec

# 제목 임베딩 "배치" 버전 (initialize_indexes에서 사용)
def get_embeddings_batch(texts):
    # 캐시에 없는 것만 모아서 한 번에 요청
    uncached = []
    keys = []
    out = []
    for t in texts:
        k = hashlib.md5((t + "|" + EMBED_MODEL).encode("utf-8")).hexdigest()
        keys.append(k)
        if k not in _embed_cache:
            uncached.append(t)

    if uncached:
        res = client.embeddings.create(input=uncached, model=EMBED_MODEL)
        idx = 0
        for t in uncached:
            vec = np.array(res.data[idx].embedding, dtype="float32").reshape(1, -1)
            k = hashlib.md5((t + "|" + EMBED_MODEL).encode("utf-8")).hexdigest()
            _embed_cache[k] = vec
            idx += 1
        _save_embed_cache(_embed_cache)

    for i, t in enumerate(texts):
        out.append(_embed_cache[keys[i]])
    return out


# -----------------------------
# 필드 정규식
# -----------------------------
FIELD_PATTERNS = {
    "신청기간": r"(?:신청\s*기간|접수\s*기간)\s*:\s*([0-9.\-~\s:()]+)",
    "대상자": r"(?:대상자|대상)\s*:\s*([^\n]+)",
    "진행기간": r"(?:진행\s*기간|일시)\s*:\s*([0-9.\-~\s:()]+)",
    "URL": r"(?:URL|링크|주소)\s*:\s*(\S+)",
    "KUM마일리지": r"(?:KUM|쿰)\s*마일리(?:지|리지)\s*([0-9]+)\s*점",
    "장소": r"(?:장소|위치)\s*:\s*([^\n]+)",
    "수료증": r"(?:수료증)\s*[:\-]?\s*(있음|없음)" 
}

# -----------------------------
# 유틸 함수
# -----------------------------
def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[^\w가-힣]", "", s)
    return s

def _normalize_sources(srcs):
    out = []
    for s in srcs or []:
        out.append({
            "id": s.get("id") or s.get("extracurricular_id"),
            "title": s.get("title", ""),
            "url": s.get("url", "")
        })
    return out

# -----------------------------
# DB 로딩
# -----------------------------

SCHEDULE_RELIABLE_DAY_THRESHOLD = 3  # 3일 이상인 경우 시간표 충돌 판단에서 사용하지 않음
SCHEDULE_EXCLUDE_KEYWORDS = ("신청기간", "접수기간", "모집기간", "모집일", "접수일")
SCHEDULE_PREFERRED_KEYWORDS = (
    "행사", "운영", "교육", "활동", "진행", "특강", "워크숍", "설명회", "프로그램 일정"
)

# 날짜/시간 포맷統一 (예: "2025.10.03 13:00")
def _fmt_dt(dt):
    if not dt:
        return ""
    if isinstance(dt, str):
        return dt  # 이미 문자열이면 그대로
    try:
        return dt.strftime("%Y.%m.%d %H:%M")
    except Exception:
        return str(dt)

def load_activities_from_db():
    """
    - is_deleted = 0 인 것만 로딩
    - RAG/규칙 추출에 유용한 필드들을 텍스트로 정리
    - 정규식 FIELD_PATTERNS에 맞도록 한글 라벨 고정:
        신청기간/진행기간/장소/URL/KUM 마일리지/수료증/대상자
    """
    with engine.connect() as conn:
        q = """
        SELECT
            extracurricular_pk_id,
            extracurricular_id,
            title,
            url,
            description,
            activity_start,
            activity_end,
            application_start,
            application_end,
            keywords,
            location,
            target_audience,
            kum_mileage,
            has_certificate,
            selection_method,
            purpose,
            benefits,
            `procedure` AS procedure_field
        FROM extracurricular
        WHERE COALESCE(is_deleted, 0) = 0
        """
        rows = []
        for r in conn.execute(sql_text(q)).mappings():
            # 안전한 값 꺼내기
            title = r.get("title", "") or ""
            url = r.get("url", "") or ""
            location = r.get("location", "") or ""
            description = r.get("description", "") or ""
            target = r.get("target_audience", "") or ""
            mileage = r.get("kum_mileage", None)
            has_cert = r.get("has_certificate", None)  # 1/0 또는 None
            sel_method = r.get("selection_method", "") or ""
            purpose = r.get("purpose", "") or ""
            benefits = r.get("benefits", "") or ""
            procedure = r.get("procedure_field", "") or ""
            keywords_raw = r.get("keywords", None)  # JSON

            # 날짜/시간 포맷 정리
            app_start = _fmt_dt(r.get("application_start"))
            app_end   = _fmt_dt(r.get("application_end"))
            act_start = _fmt_dt(r.get("activity_start"))
            act_end   = _fmt_dt(r.get("activity_end"))

            # 수료증 표기(정규식에 맞추어 '있음|없음')
            cert_line = None
            if has_cert is not None:
                cert_line = f"수료증: {'있음' if int(has_cert) == 1 else '없음'}"

            # 마일리지 표기(정규식에 맞추어 “… 10점”)
            mileage_line = None
            if mileage is not None:
                mileage_line = f"KUM 마일리지 {int(mileage)}점"

            # 키워드(JSON) 가공(선택)
            keywords_line = None
            keywords_for_storage = keywords_raw
            if keywords_raw:
                try:
                    # keywords가 JSON 배열이라고 가정
                    if isinstance(keywords_raw, (list, tuple)):
                        kw_list = keywords_raw
                    else:
                        # sqlalchemy가 str로 줄 때 대비
                        import json
                        kw_list = json.loads(keywords_raw)
                    if kw_list:
                        keywords_line = "키워드: " + ", ".join(map(str, kw_list))
                        keywords_for_storage = kw_list
                except Exception:
                    keywords_line = str(keywords_raw)

            # 규칙 기반 추출에 걸리도록 한글 라벨 고정
            text_lines = [
                f"제목: {title}",
                f"URL: {url}" if url else "",
                f"신청기간: {app_start}~{app_end}" if (app_start or app_end) else "",
                f"진행기간: {act_start}~{act_end}" if (act_start or act_end) else "",
                f"장소: {location}" if location else "",
                f"대상자: {target}" if target else "",
                mileage_line or "",
                cert_line or "",
                f"선정방법: {sel_method}" if sel_method else "",
                f"목적: {purpose}" if purpose else "",
                f"혜택: {benefits}" if benefits else "",
                f"절차: {procedure}" if procedure else "",
                keywords_line or "",
                description,  # 맨 마지막에 본문 설명
            ]

            text = "\n".join([ln for ln in text_lines if ln])

            rows.append({
                # 내부 id는 이전 코드와의 호환을 위해 extracurricular_id 유지
                "id": r["extracurricular_id"],
                "title": title,
                "url": url,
                "text": text,
                # [CHANGED STEP1] 관심사 매칭 강화를 위해 추가 필드 저장
                "description": description,
                "keywords": keywords_for_storage,
                "purpose": purpose,
                "act_start_dt": r.get("activity_start"),
                "act_end_dt": r.get("activity_end"),
            })
        return rows

# -----------------------------
# 청크화 + 인덱싱
# -----------------------------
def chunk_text(text: str, chunk_size: int = 700, overlap: int = 20):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i+chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks

# Agent_Rag_Chatbot.py

# [CHANGED STEP1] 프로그램 텍스트 구성 헬퍼
def build_program_text(activity: dict) -> str:
    parts = []
    if activity.get("title"):
        parts.append(activity["title"])
    if activity.get("description"):
        parts.append(activity["description"])
    kw = activity.get("keywords")
    if kw:
        if isinstance(kw, (list, tuple, set)):
            parts.append(" ".join(map(str, kw)))
        else:
            parts.append(str(kw))
    if activity.get("purpose"):
        parts.append(activity["purpose"])
    return " ".join(parts)

def initialize_indexes():
    # 1) 인덱스/메타가 이미 있으면, DB는 로드하되 청크 임베딩 재계산/재인덱싱은 스킵
    if FAISS_INDEX_FILE.exists() and CHUNK_META_FILE.exists():
        _ = faiss.read_index(str(FAISS_INDEX_FILE))
        with open(CHUNK_META_FILE, "rb") as f:
            _ = pickle.load(f)

        activities_local = load_activities_from_db()

        # [CHANGED STEP1] 확장된 프로그램 텍스트 기반 임베딩
        prog_texts = [build_program_text(a) for a in activities_local]
        program_embeddings_local = get_embeddings_batch(prog_texts)
        return activities_local, program_embeddings_local

    # 2) 없을 때만 (처음 한 번) 빌드
    activities_local = load_activities_from_db()
    prog_texts = [build_program_text(a) for a in activities_local]
    program_embeddings_local = get_embeddings_batch(prog_texts)

    chunk_texts, chunk_meta = [], []
    for act in activities_local:
        for ck in chunk_text(act["text"]):
            chunk_texts.append(ck)
            chunk_meta.append({"id": act["id"], "title": act["title"], "url": act["url"], "chunk": ck})

    if chunk_texts:
        chunk_embs = np.vstack([get_embedding(ck) for ck in chunk_texts]).astype("float32")
        chunk_embs /= np.linalg.norm(chunk_embs, axis=1, keepdims=True) + 1e-12
        index = faiss.IndexFlatIP(chunk_embs.shape[1])
        index.add(chunk_embs)
        faiss.write_index(index, str(FAISS_INDEX_FILE))
        with open(CHUNK_META_FILE, "wb") as f:
            pickle.dump(chunk_meta, f)

    return activities_local, program_embeddings_local

def load_indexes():
    if FAISS_INDEX_FILE.exists() and CHUNK_META_FILE.exists():
        index = faiss.read_index(str(FAISS_INDEX_FILE))
        with open(CHUNK_META_FILE, "rb") as f:
            meta = pickle.load(f)
        return index, meta
    return None, None

# -----------------------------
# 스케줄 파싱 (날짜 포함)
# -----------------------------
# 요일 매핑: 0=월 ... 6=일
_KOR_WEEKDAY = {"월":0,"화":1,"수":2,"목":3,"금":4,"토":5,"일":6}

def _weekday_of(dt: datetime) -> int:
    return dt.weekday()  # 월=0 ... 일=6

def _overlap_by_weekday(schedule, slot):
    """
    schedule: {'start': dt, 'end': dt, 'reliable': bool}
    slot: {'day':'월','startTime':'HH:MM','endTime':'HH:MM'}
    """
    if not schedule:
        return False
    if not schedule.get("reliable", True):
        return False
    try:
        w = _KOR_WEEKDAY.get((slot.get("day") or "").strip())
        if w is None:
            return False
        start_date = schedule["start"].date()
        end_date = schedule["end"].date()
        duration_days = (end_date - start_date).days
        if duration_days >= SCHEDULE_RELIABLE_DAY_THRESHOLD:
            return False
        for d in range(duration_days + 1):
            day_dt = start_date + timedelta(days=d)
            if day_dt.weekday() != w:
                continue
            if d == 0:
                a_start = schedule["start"].strftime("%H:%M")
                a_end = "23:59" if duration_days > 0 else schedule["end"].strftime("%H:%M")
            elif d == duration_days:
                a_start = "00:00"
                a_end = schedule["end"].strftime("%H:%M")
            else:
                a_start, a_end = "00:00", "23:59"
            if _time_overlap_only(a_start, a_end, slot.get("startTime","00:00"), slot.get("endTime","00:00")):
                return True
        return False
    except Exception:
        return False

SCHEDULE_PATTERNS = [
    r"(\d{4}[.\-\/]\d{2}[.\-\/]\d{2})\s+(\d{2}:\d{2})\s*~\s*(\d{4}[.\-\/]\d{2}[.\-\/]\d{2})\s+(\d{2}:\d{2})"
]

def _parse_date(s: str) -> datetime.date:
    for fmt in ("%Y.%m.%d", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"지원하지 않는 날짜 형식: {s}")

def _parse_datetime(date_str: str, time_str: str) -> datetime:
    # Asia/Seoul 기준 로컬 naive datetime으로 처리
    return datetime.combine(_parse_date(date_str), datetime.strptime(time_str, "%H:%M").time())

def parse_schedule(text: str):
    """
    활동 텍스트에서 '시작~종료'를 날짜 포함으로 파싱.
    반환: {'start': datetime, 'end': datetime, 'reliable': bool} 또는 None
    """
    if not text:
        return None

    preferred_lines = []
    fallback_lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if any(keyword in line for keyword in SCHEDULE_EXCLUDE_KEYWORDS):
            continue
        if any(keyword in line for keyword in SCHEDULE_PREFERRED_KEYWORDS):
            preferred_lines.append(line)
        else:
            fallback_lines.append(line)

    search_spaces = preferred_lines + fallback_lines
    for chunk in search_spaces:
        for pat in SCHEDULE_PATTERNS:
            m = re.search(pat, chunk)
            if not m:
                continue
            s_date, s_time, e_date, e_time = m.group(1), m.group(2), m.group(3), m.group(4)
            start_dt = _parse_datetime(s_date, s_time)
            end_dt = _parse_datetime(e_date, e_time)
            duration_days = (end_dt.date() - start_dt.date()).days
            reliable = duration_days < SCHEDULE_RELIABLE_DAY_THRESHOLD
            if not reliable:
                return {"start": start_dt, "end": end_dt, "reliable": False}
            return {"start": start_dt, "end": end_dt, "reliable": True}
    return None

def _overlap_dt(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return max(a_start, b_start) < min(a_end, b_end)

def _time_overlap_only(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    """날짜 정보가 없을 때(역호환): 시:분만으로 겹침 판단"""
    fmt = "%H:%M"
    s1, e1 = datetime.strptime(a_start, fmt), datetime.strptime(a_end, fmt)
    s2, e2 = datetime.strptime(b_start, fmt), datetime.strptime(b_end, fmt)
    return max(s1, s2) < min(e1, e2)
    


# -----------------------------
# 글로벌 상태 (후속질의 맥락)
# -----------------------------
activities = []
program_embeddings = []  # [CHANGED STEP1] 확장 텍스트 임베딩 캐시
recent_top5_idx_title_map = {}
recent_top5_idx_id_map = {}   # 후속 질의에 쓸 수 있는 id
last_queried_title = None

# -----------------------------
# 필드 추출 & 단답
# -----------------------------
def extract_fields(text: str) -> dict:
    out = {}
    for k, pat in FIELD_PATTERNS.items():
        m = re.search(pat, text)
        if m:
            out[k] = m.group(1).strip()
    return out

def _short_field_answer(query: str, fields: dict):
    for k in FIELD_PATTERNS.keys():
        if k in query and fields.get(k):
            return f"{k}: {fields[k]}"
    return None

def answer_program_question_by_title(query: str):
    global last_queried_title
    for act in activities:
        if _normalize(act["title"]) in _normalize(query) or (last_queried_title and _normalize(last_queried_title) in _normalize(query)):
            fields = extract_fields(act["text"])
            short = _short_field_answer(query, fields)
            if short:
                return short
            # fallback LLM
            prompt = f"[활동정보]\n{act['text']}\n\n[질문]\n{query}\n\n자료에 기반해 1~2문장으로 답하세요."
            resp = client.chat.completions.create(
                model="gpt-3.5-turbo", temperature=0, max_tokens=150,
                messages=[{"role":"system","content":"간단한 비교과 안내 도우미"},
                          {"role":"user","content":prompt}]
            )
            return resp.choices[0].message.content.strip()
    return "자료에 없음"

# -----------------------------
# 추천 검색 (Top-5) - 시간표 필터 부분만 교체
# -----------------------------
def _convert_candidates_to_output(candidates, topk=5):
    if not candidates:
        return "", [], []
    ordered = sorted(candidates, key=lambda x: x[3], reverse=True)[:topk]
    text_out = "\n".join([f"{i+1}. {t}" for i, (_, _, t, _) in enumerate(ordered)])
    ids_out = [tid for _, tid, _, _ in ordered]
    structured = []
    for idx, tid, title, _ in ordered:
        act = activities[idx]
        structured.append({
            "id": tid,
            "title": title,
            "url": act.get("url", "")
        })
    return text_out, ids_out, structured

def _summarize_timetable_slots(slots):
    if not slots:
        return "없음"
    formatted = []
    for slot in slots:
        if {"day","startTime","endTime"} <= set(slot.keys()):
            formatted.append(f"{slot['day']} {slot['startTime']}~{slot['endTime']}")
        elif {"start","end"} <= set(slot.keys()):
            formatted.append(f"{slot['start']}~{slot['end']}")
        elif {"startDay","startTime","endDay","endTime"} <= set(slot.keys()):
            formatted.append(f"{slot['startDay']} {slot['startTime']}~{slot['endDay']} {slot['endTime']}")
        elif slot.get("startTime") and slot.get("endTime"):
            formatted.append(f"{slot['startTime']}~{slot['endTime']}")
    return ", ".join(formatted) if formatted else "없음"

def _build_profile_hint(user_profile):
    interests = ", ".join(user_profile.get("interests", [])) if user_profile.get("interests") else "없음"
    busy = _summarize_timetable_slots(user_profile.get("timetable") or [])
    lines = [f"관심사: {interests}"]
    if busy != "없음":
        lines.append(f"제약 시간대: {busy}")
    return "\n".join(lines)

def _build_program_schedule(act: dict):
    """
    act: program dict
    return: {'start': datetime, 'end': datetime, 'reliable': bool} or None
    """
    start_dt = act.get("act_start_dt")
    end_dt = act.get("act_end_dt")
    if start_dt and end_dt:
        duration_days = (end_dt.date() - start_dt.date()).days
        reliable = duration_days < SCHEDULE_RELIABLE_DAY_THRESHOLD
        return {"start": start_dt, "end": end_dt, "reliable": reliable}
    return parse_schedule(act.get("text"))

def search_top5_programs_with_explanation(query: str, user_profile: dict):
    global recent_top5_idx_title_map, recent_top5_idx_id_map, last_queried_title

    # (지연 초기화) activities가 비었으면 초기화
    global activities, program_embeddings
    if not activities or not program_embeddings:
        activities, program_embeddings = initialize_indexes()

    interest_text = " ".join(user_profile.get("interests", [])) if user_profile.get("interests") else ""
    query_for_emb = query
    if interest_text:
        query_for_emb = f"{query.strip()} 관심사: {interest_text}"
    query_emb = get_embedding(query_for_emb)
    interest_emb = get_embedding(interest_text) if interest_text else None

    mileage_filter = None
    m = re.search(r"마일리(?:지|리지)\s*(\d+)", query)
    if m: mileage_filter = int(m.group(1))

    alpha, beta = 0.8, 0.2
    generic_queries = {"비교과 추천해줘", "비교과 추천", "비교과 뭐 있어?", "비교과 활동 추천해줘"}
    if query.strip() in generic_queries:
        alpha, beta = 0.5, 0.5

    scored = []
    scored_all = []
    for idx, act in enumerate(activities):
        schedule = _build_program_schedule(act)  # {'start': dt, 'end': dt} 또는 None

        # --- 날짜/요일 포함 겹침 체크 ---
        has_conflict = False
        user_slots = user_profile.get("timetable") or []
        if schedule and schedule.get("reliable", True):
            for slot in user_slots:
                try:
                    if "start" in slot and "end" in slot:
                        # 날짜 포함 슬롯: "YYYY-MM-DD HH:MM"
                        def _parse_slot_dt(s):
                            s = s.strip().replace("/", "-").replace(".", "-")
                            return datetime.strptime(s, "%Y-%m-%d %H:%M")
                        b_start = _parse_slot_dt(slot["start"])
                        b_end   = _parse_slot_dt(slot["end"])
                        if _overlap_dt(schedule["start"], schedule["end"], b_start, b_end):
                            has_conflict = True
                            break
                    elif {"startDay","startTime","endDay","endTime"} <= set(slot.keys()):
                        # 날짜/시간 분리 슬롯
                        b_start = _parse_datetime(slot["startDay"].replace("-", ".").replace("/", "."), slot["startTime"])
                        b_end   = _parse_datetime(slot["endDay"].replace("-", ".").replace("/", "."), slot["endTime"])
                        if _overlap_dt(schedule["start"], schedule["end"], b_start, b_end):
                            has_conflict = True
                            break
                    elif {"day","startTime","endTime"} <= set(slot.keys()):
                        # 요일 기반 슬롯
                        if _overlap_by_weekday(schedule, slot):
                            has_conflict = True
                            break
                    else:
                        # 날짜 없는 구형 슬롯: {'startTime':'HH:MM','endTime':'HH:MM'}
                        if _time_overlap_only(schedule["start"].strftime("%H:%M"),
                                              schedule["end"].strftime("%H:%M"),
                                              slot.get("startTime","00:00"),
                                              slot.get("endTime","00:00")):
                            has_conflict = True
                            break
                except Exception:
                    pass
        # --- 마일리지 필터 ---
        fields = extract_fields(act["text"])
        if mileage_filter and int(fields.get("KUM마일리지","0")) != mileage_filter:
            continue

        # --- 스코어 ---
        prog_emb = program_embeddings[idx]
        qsim = float(cosine_similarity(prog_emb, query_emb)[0][0])
        isim = float(cosine_similarity(prog_emb, interest_emb)[0][0]) if interest_emb is not None else 0.0
        score = alpha*qsim + beta*isim
        candidate = (idx, act["id"], act["title"], score)
        scored_all.append(candidate)
        if not has_conflict:
            scored.append(candidate)

    reco_text, ids_out, structured = _convert_candidates_to_output(scored)
    fallback_text, _, fallback_structured = _convert_candidates_to_output(scored_all)

    if structured:
        recent_top5_idx_title_map = {i+1: item["title"] for i, item in enumerate(structured)}
        recent_top5_idx_id_map    = {i+1: item["id"] for i, item in enumerate(structured)}
        last_queried_title = structured[0]["title"]

    return reco_text, ids_out, structured, fallback_structured, fallback_text

# -----------------------------
# 청크 기반 RAG 검색
# -----------------------------
def search_chunks(query: str, topk=5):
    index, meta = load_indexes()
    if not index: return []
    q_emb = get_embedding(query).astype("float32")
    q_emb /= np.linalg.norm(q_emb, axis=1, keepdims=True) + 1e-12  # 쿼리도 정규화
    D, I = index.search(q_emb, topk)  # IP 점수 = 코사인 유사도와 단조 일치
    return [meta[i] for i in I[0] if i < len(meta)]

def build_context(chunks): 
    return "\n\n".join(c["chunk"] for c in chunks)[:2000]

def generate_answer(query, context, sources):
    prompt = f"질문: {query}\n\n참고자료:\n{context}\n\n위 자료만 근거로 답하세요."
    resp = client.chat.completions.create(
        model="gpt-3.5-turbo", temperature=0,
        messages=[{"role":"system","content":"비교과 챗봇"},{"role":"user","content":prompt}]
    )
    ans = resp.choices[0].message.content.strip()
    return {"answer": ans, "sources": [{"id": s["id"], "title": s["title"], "url": s["url"]} for s in sources]}

# -----------------------------
# 평가 스크립트
# -----------------------------
def evaluate(golden, user_profile):
    hits, mrr, ndcg, recall1, total = 0,0,0,0,0
    for g in golden:
        q, expected = g["query"], g["expected_title"]
        _, _, recos, _, _ = search_top5_programs_with_explanation(q, user_profile)
        titles = [r["title"] for r in recos]
        total += 1
        if expected in titles: hits += 1
        if expected in titles[:1]: recall1 += 1
        if expected in titles:
            rank = titles.index(expected)+1
            mrr += 1.0/rank
            ndcg += 1.0/np.log2(rank+1)
    return {
        "hit@5": hits/total, "MRR@5": mrr/total,
        "nDCG@5": ndcg/total, "Recall@1": recall1/total
    }

def _demo_conflict_logic():
    """
    간단한 더미 데이터를 통해 시간표 충돌 판단이 의도대로 동작하는지 확인.
    RUN_CONFLICT_DEMO=1 환경변수와 함께 직접 실행하면 결과를 확인할 수 있다.
    """
    user_slots = [{"day": "목", "startTime": "13:00", "endTime": "14:00"}]
    dummy_programs = [
        {
            "id": 100,
            "title": "짧은 목요일 특강",
            "act_start_dt": datetime(2025, 5, 29, 13, 30),
            "act_end_dt": datetime(2025, 5, 29, 15, 0),
            "text": ""
        },
        {
            "id": 200,
            "title": "5일간 진행되는 장기 프로그램",
            "act_start_dt": datetime(2025, 5, 1, 0, 0),
            "act_end_dt": datetime(2025, 5, 5, 23, 59),
            "text": ""
        },
        {
            "id": 300,
            "title": "텍스트 기반 일정",
            "text": "신청기간: 2025.05.01 00:00~2025.05.20 23:59\n행사일: 2025.05.30 13:00~2025.05.30 15:00"
        }
    ]

    for prog in dummy_programs:
        schedule = _build_program_schedule(prog)
        slot = user_slots[0]
        conflict = False
        if schedule and schedule.get("reliable", True):
            conflict = _overlap_by_weekday(schedule, slot)
        print(f"[데모] {prog['title']} -> schedule={schedule}, conflict={conflict}")

# -----------------------------
# FastAPI 연동용 Wrapper
# -----------------------------
def initialize_activities():
    global activities, program_embeddings
    activities, program_embeddings = initialize_indexes()

def api_run(user_profile: dict, user_question: str):
    # 필드 기반 질문이면 우선 처리
    field_answer = answer_program_question_by_title(user_question)
    if field_answer != "자료에 없음":
        return {"answer": field_answer, "sources": []}

    # 추천 Top-5
    reco_text, _, reco_structured, fallback_structured, fallback_text = search_top5_programs_with_explanation(user_question, user_profile)
    if reco_structured:
        return {"answer": reco_text, "sources": _normalize_sources(reco_structured)}
    
    if fallback_structured:
        interests_desc = ", ".join(user_profile.get("interests", [])) if user_profile.get("interests") else "없음"
        busy_desc = _summarize_timetable_slots(user_profile.get("timetable") or [])
        notice_lines = [
            "사용자 시간표와 겹치지 않는 비교과는 찾지 못했습니다.",
            f"관심사: {interests_desc}"
        ]
        if busy_desc != "없음":
            notice_lines.append(f"등록된 바쁜 시간: {busy_desc}")
        notice_lines.append("아래 프로그램은 시간표 충돌이 있지만 관심사에 가까운 참고용 추천입니다.")
        fallback_answer = "\n".join(notice_lines) + "\n\n" + fallback_text
        return {"answer": fallback_answer, "sources": _normalize_sources(fallback_structured)}

    # RAG 검색
    chunks = search_chunks(user_question, topk=5)
    if not chunks:
        return {"answer": "조건에 맞는 자료를 찾을 수 없습니다.", "sources": []}
    context = build_context(chunks)
    
    profile_hint = _build_profile_hint(user_profile)
    enriched_question = f"{user_question}\n\n[사용자 프로필]\n{profile_hint}" if profile_hint else user_question
    rag = generate_answer(enriched_question, context, chunks)   
    rag["sources"] = _normalize_sources(rag.get("sources")) 
    return rag

if __name__ == "__main__" and os.getenv("RUN_CONFLICT_DEMO") == "1":
    _demo_conflict_logic()