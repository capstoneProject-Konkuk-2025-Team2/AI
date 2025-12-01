# graph/embedding_topic_match.py

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

import os
from urllib.parse import quote_plus

import numpy as np
from sqlalchemy import create_engine, text
from neo4j import GraphDatabase
from openai import OpenAI

# ---------- Env & Client ----------
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not NEO4J_PASSWORD:
    raise RuntimeError("NEO4J_PASSWORD 가 .env에 없습니다.")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY 가 .env에 없습니다.")

HOST = os.getenv("HOST")
PORT = os.getenv("PORT", "3306")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
DBNAME = os.getenv("DBNAME")

missing = [k for k, v in {"HOST": HOST, "USERNAME": USERNAME, "PASSWORD": PASSWORD, "DBNAME": DBNAME}.items() if not v]
if missing:
    raise RuntimeError(f".env 누락: {', '.join(missing)}")

PASSWORD_Q = quote_plus(str(PASSWORD))
DATABASE_URL = f"mysql+pymysql://{USERNAME}:{PASSWORD_Q}@{HOST}:{PORT}/{DBNAME}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
client = OpenAI(api_key=OPENAI_API_KEY)

EMBED_MODEL = "text-embedding-3-small"
SIM_THRESHOLD = 0.40  # 일단 0.4로 시작, 나중에 조절


# ---------- Topic 설정 ----------
# 이름 + 설명(aliases) 정도만 써두면 됨. 필요하면 여기 계속 추가하면 돼.
TOPIC_DEFS = [
    {
        "name": "AI",
        "text": "AI 인공지능 머신러닝 딥러닝 데이터사이언스 알고리즘 모델 개발"
    },
    {
        "name": "데이터",
        "text": "데이터 데이터분석 빅데이터 통계 시각화 데이터처리"
    },
    {
        "name": "진로",
        "text": "진로 커리어 탐색 취업 진로설계 자기계발"
    },
    {
        "name": "마케팅",
        "text": "마케팅 브랜딩 캠페인 홍보 콘텐츠 SNS 광고"
    },
    {
        "name": "프론트엔드",
        "text": "프론트엔드 웹 프론트 React JavaScript UI UX"
    },
    {
        "name": "백엔드",
        "text": "백엔드 서버 API 데이터베이스 Spring Django"
    },
    {
        "name": "DevOps",
        "text": "DevOps CI CD 클라우드 배포 인프라 모니터링"
    },
    {
        "name": "DB",
        "text": "DB 데이터베이스 SQL 설계 튜닝 저장소"
    },
]


# ---------- Helper: OpenAI Embedding ----------
def get_embeddings(texts):
    """
    texts: List[str]
    return: np.ndarray shape (n, d)
    """
    # 빈 문자열은 모델이 싫어하니까 최소한의 placeholder
    safe_texts = [t if t.strip() else " " for t in texts]
    resp = client.embeddings.create(model=EMBED_MODEL, input=safe_texts)
    vecs = [d.embedding for d in resp.data]
    return np.array(vecs, dtype="float32")


# ---------- Main Logic ----------
def fetch_programs():
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
              extracurricular_id       AS program_id,
              title,
              description,
              keywords,
              purpose,
              benefits,
              `procedure`
            FROM extracurricular
            WHERE is_deleted = 0
        """)).mappings().all()

    programs = []
    for r in rows:
        parts = []

        for col in ["title", "description", "purpose", "benefits", "procedure"]:
            v = r.get(col)
            if v:
                parts.append(str(v))

        # keywords(JSON) → 문자열로 펼치기
        kw = r.get("keywords")
        if kw:
            # MySQL JSON이 문자열로 들어올 수 있으니, 그냥 괄호/따옴표 제거하고 붙이기
            parts.append(str(kw))

        text_all = "\n".join(parts)
        programs.append({
            "id": r["program_id"],
            "text": text_all
        })

    return programs


def compute_program_topic_matches(programs, topics):
    """
    programs: [{"id":..., "text":...}, ...]
    topics:   [{"name":..., "text":..., "embedding": np.array}, ...]

    return: [(program_id, topic_name, sim_float), ...]
    """
    # 1) Program embedding (batch)
    prog_texts = [p["text"] for p in programs]
    print(f"➡ Program {len(prog_texts)}개 임베딩 생성 중...")
    prog_emb = get_embeddings(prog_texts)
    # L2 정규화
    prog_emb = prog_emb / (np.linalg.norm(prog_emb, axis=1, keepdims=True) + 1e-8)

    # 2) Topic embedding
    topic_texts = [t["text"] for t in topics]
    print(f"➡ Topic {len(topic_texts)}개 임베딩 생성 중...")
    topic_emb = get_embeddings(topic_texts)
    topic_emb = topic_emb / (np.linalg.norm(topic_emb, axis=1, keepdims=True) + 1e-8)

    # 3) 코사인 유사도: (n_prog, n_topic)
    sim_matrix = prog_emb @ topic_emb.T

    matches = []
    for i, p in enumerate(programs):
        for j, t in enumerate(topics):
            sim = float(sim_matrix[i, j])
            if sim >= SIM_THRESHOLD:
                matches.append((p["id"], t["name"], sim))

    print(f"✅ {len(matches)}개의 Program–Topic 매칭 생성 (threshold={SIM_THRESHOLD})")
    return matches


def write_matches_to_neo4j(matches):
    """
    matches: [(program_id, topic_name, sim), ...]
    """

    def tx_clear_embedding_edges(tx):
        # embedding 기반으로 만든 기존 HAS_TOPIC만 삭제
        tx.run("""
        MATCH (:Program)-[r:HAS_TOPIC]->(:Topic)
        WHERE r.source = "embedding"
        DELETE r
        """)

    def tx_apply_matches(tx, batch):
        for program_id, topic_name, sim in batch:
            tx.run("""
            MATCH (p:Program {id:$pid})
            MERGE (t:Topic {name:$tname})
            MERGE (p)-[r:HAS_TOPIC]->(t)
            SET r.sim = $sim,
                r.source = "embedding"
            """, pid=program_id, tname=topic_name, sim=sim)

    with driver.session() as session:
        print("➡ 이전 embedding 기반 HAS_TOPIC 관계 삭제 중...")
        session.execute_write(tx_clear_embedding_edges)

        print("➡ 새 매칭을 Neo4j에 반영 중...")
        BATCH_SIZE = 100
        for idx in range(0, len(matches), BATCH_SIZE):
            batch = matches[idx: idx + BATCH_SIZE]
            session.execute_write(tx_apply_matches, batch)
        print("✅ Neo4j 반영 완료")


if __name__ == "__main__":
    print("=== Embedding 기반 Program–Topic 매핑 시작 ===")
    programs = fetch_programs()
    print(f"Program 수: {len(programs)}")

    # Topic 정의에 name만 붙여서 넘기기
    topics = [{"name": t["name"], "text": t["text"]} for t in TOPIC_DEFS]

    matches = compute_program_topic_matches(programs, topics)
    write_matches_to_neo4j(matches)
    print("🎉 Embedding 매핑 전체 완료")