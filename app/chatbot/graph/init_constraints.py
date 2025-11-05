# graph/init_constraints.py
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

def create_constraints(tx):
    tx.run("CREATE CONSTRAINT program_id  IF NOT EXISTS FOR (p:Program)    REQUIRE p.id   IS UNIQUE")
    tx.run("CREATE CONSTRAINT member_id   IF NOT EXISTS FOR (m:Member)     REQUIRE m.id   IS UNIQUE")
    tx.run("CREATE CONSTRAINT topic_name  IF NOT EXISTS FOR (t:Topic)      REQUIRE t.name IS UNIQUE")
    tx.run("CREATE CONSTRAINT busy_id     IF NOT EXISTS FOR (b:BusyBlock)  REQUIRE b.id   IS UNIQUE")
    tx.run("CREATE CONSTRAINT dept_name   IF NOT EXISTS FOR (d:Dept)      REQUIRE d.name IS UNIQUE")

with driver.session() as session:
    session.execute_write(create_constraints)

print("Neo4j 제약조건 생성 완료")