// 1) Program의 텍스트를 하나로 합치기
MATCH (p:Program)
WITH p, toLower(
  coalesce(p.title, '') + ' ' +
  coalesce(p.description, '') + ' ' +
  coalesce(p.purpose, '') + ' ' +
  coalesce(p.benefits, '') + ' ' +
  coalesce(p.keywords, '')
) AS txt

// 2) AI 관련 토픽
FOREACH (_ IN CASE WHEN txt CONTAINS 'ai'
                     OR txt CONTAINS '인공지능'
                     OR txt CONTAINS '머신러닝'
                   THEN [1] ELSE [] END |
  MERGE (t:Topic {name: 'AI'})
  MERGE (p)-[:HAS_TOPIC]->(t)
)

// 3) 진로/취업 관련 토픽
FOREACH (_ IN CASE WHEN txt CONTAINS '진로'
                     OR txt CONTAINS '취업'
                     OR txt CONTAINS '면접'
                   THEN [1] ELSE [] END |
  MERGE (t:Topic {name: '진로'})
  MERGE (p)-[:HAS_TOPIC]->(t)
)

// 4) 마일리지 관련 토픽
FOREACH (_ IN CASE WHEN txt CONTAINS '마일리지'
                   THEN [1] ELSE [] END |
  MERGE (t:Topic {name: '마일리지'})
  MERGE (p)-[:HAS_TOPIC]->(t)
);