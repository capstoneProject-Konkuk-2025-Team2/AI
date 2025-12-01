:param memberId => 4;

// 1) 관심 Topic 기반으로 Program 후보 찾기 + 시간표 무충돌 필터
WITH $memberId AS mid
MATCH (m:Member {id: mid})-[:INTERESTS]->(t:Topic)
MATCH (p:Program)-[:HAS_TOPIC]->(t)
WHERE NOT EXISTS {
  MATCH (m)-[:HAS_BUSY]->(b:BusyBlock)
  WITH m, p, b,
       CASE toUpper(b.day)
         WHEN 'MON' THEN 1 WHEN 'TUE' THEN 2 WHEN 'WED' THEN 3
         WHEN 'THU' THEN 4 WHEN 'FRI' THEN 5 WHEN 'SAT' THEN 6 ELSE 7
       END AS bDow
  WHERE bDow = date(p.act_start).dayOfWeek
    AND time(p.act_start) < b.end_time
    AND time(p.act_end)   > b.start_time
}
WITH m, p, count(t) AS score
RETURN p.id AS program_id,
       p.title AS title,
       p.act_start AS act_start,
       p.act_end AS act_end,
       score
ORDER BY score DESC, act_start
LIMIT 20;