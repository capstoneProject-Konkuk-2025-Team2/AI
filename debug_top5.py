# debug_top5.py (임시 스크립트)
from sqlalchemy import text as sql_text
from app.utils.db import engine

sql = """
SELECT extracurricular_id, title, url, description,
       activity_start, activity_end, application_start, application_end, location
FROM extracurricular
ORDER BY extracurricular_id
LIMIT 5
"""

with engine.connect() as conn:
    rows = list(conn.execute(sql_text(sql)).mappings())
    for r in rows:
        print(
            f"[{r['extracurricular_id']}] {r['title']}\n"
            f"  신청: {r['application_start']} ~ {r['application_end']}\n"
            f"  진행: {r['activity_start']} ~ {r['activity_end']}\n"
            f"  장소: {r['location']}\n"
            f"  URL : {r['url']}\n"
            f"  desc: {(r['description'] or '')[:120]}...\n"
        )