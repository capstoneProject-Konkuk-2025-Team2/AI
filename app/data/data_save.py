import json
import re
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
import mysql.connector
from mysql.connector import Error

# -------------------- 설정/상수 --------------------

AMBIGUOUS_LOCATION_PATTERNS = [
    r'및\s*수강\s*안내\s*진행\s*예정',
    r'안내\s*예정',
    r'추후\s*(별도\s*)?공지\s*예정',
    r'추후\s*안내',
    r'미정',
    r'추후\s*공지',
    r'공지\s*예정'
]
AMBIGUOUS_LOCATION_NORMALIZED = '추후 별도 공지 예정'

# 단일 출처 DDL (드랍/최초 생성에서 동일하게 사용)
TABLE_DDL = """
CREATE TABLE extracurricular (
  extracurricular_pk_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  -- 비교과 '고유아이디' (자동 증가 아님, 외부에서 주어지는 값 / 없으면 앱에서 PK로 채움)
  extracurricular_id BIGINT UNSIGNED UNIQUE,
  title VARCHAR(100) NOT NULL,
  url VARCHAR(500),
  description TEXT,
  activity_start DATETIME(6),
  activity_end DATETIME(6),
  application_start DATETIME(6),
  application_end DATETIME(6),
  keywords JSON,
  location VARCHAR(255),
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (extracurricular_pk_id),
  KEY idx_activity_start (activity_start),
  KEY idx_application_start (application_start)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

class ExtracurricularParser:
    def __init__(self, db_config: Dict[str, str]):
        """
        db_config 예시
        {
            'host': '127.0.0.1',
            'database': 'your_db',
            'user': 'root',
            'password': '1234',
            'port': 3306
        }
        """
        self.db_config = db_config
        self.setup_database()

    # ---------------- DB ----------------

    def get_connection(self):
        """MySQL 연결 생성"""
        try:
            connection = mysql.connector.connect(**self.db_config)
            return connection
        except Error as e:
            print(f"MySQL 연결 오류: {e}")
            return None

    def drop_and_recreate_table(self, force_drop=False):
        """기존 테이블 삭제 후 재생성"""
        connection = self.get_connection()
        if not connection:
            return False
        cursor = connection.cursor()
        try:
            # 기존 테이블 확인
            cursor.execute("""
                SELECT TABLE_NAME 
                FROM information_schema.tables 
                WHERE table_schema = %s AND table_name = 'extracurricular'
            """, (self.db_config['database'],))
            table_exists = cursor.fetchone() is not None
            
            if table_exists:
                if not force_drop:
                    # 데이터 수 확인
                    cursor.execute("SELECT COUNT(*) FROM extracurricular")
                    count = cursor.fetchone()[0]
                    print(f"기존 테이블에 {count}개 데이터가 있습니다.")
                    
                    confirm = input("정말로 기존 테이블을 삭제하시겠습니까? (y/N): ")
                    if confirm.lower() != 'y':
                        print("작업이 취소되었습니다.")
                        return False
                
                print("기존 테이블을 삭제합니다...")
                cursor.execute("DROP TABLE IF EXISTS extracurricular")
                print("기존 테이블 삭제 완료")
            
            # 새 테이블 생성
            cursor.execute(TABLE_DDL)
            connection.commit()
            print("새 테이블 생성 완료 (PK 101부터 시작)")
            return True
        except Error as e:
            print(f"테이블 재생성 오류: {e}")
            return False
        finally:
            cursor.close()
            connection.close()

    def setup_database(self):
        """테이블/인덱스 준비 (없으면 생성)"""
        connection = self.get_connection()
        if not connection:
            return
        cursor = connection.cursor()
        try:
            # 테이블 존재 확인
            cursor.execute("""
                SELECT TABLE_NAME 
                FROM information_schema.tables 
                WHERE table_schema = %s AND table_name = 'extracurricular'
            """, (self.db_config['database'],))
            table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                cursor.execute(TABLE_DDL)
                connection.commit()
                print("새 테이블 생성 완료")
            else:
                print("기존 테이블이 존재합니다.")
        except Error as e:
            print(f"테이블 생성 오류: {e}")
        finally:
            cursor.close()
            connection.close()

    def check_table_exists(self):
        """테이블 존재 여부 및 스키마 확인"""
        connection = self.get_connection()
        if not connection:
            return False
        cursor = connection.cursor()
        try:
            cursor.execute("""
                SELECT TABLE_NAME 
                FROM information_schema.tables 
                WHERE table_schema = %s AND table_name = 'extracurricular'
            """, (self.db_config['database'],))
            table_exists = cursor.fetchone() is not None

            if table_exists:
                print("✓ extracurricular 테이블이 존재합니다.")

                cursor.execute("""
                    SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_KEY, EXTRA
                    FROM information_schema.columns 
                    WHERE table_schema = %s AND table_name = 'extracurricular'
                    ORDER BY ORDINAL_POSITION
                """, (self.db_config['database'],))
                columns = cursor.fetchall()

                print("\n현재 테이블 스키마:")
                print("컬럼명 | 데이터타입 | NULL허용 | 기본값 | KEY | EXTRA")
                print("-" * 80)
                for col in columns:
                    name, data_type, is_nullable, default_value, column_key, extra = col
                    default_val = str(default_value) if default_value is not None else "없음"
                    print(f"{name} | {data_type} | {is_nullable} | {default_val} | {column_key} | {extra}")
            else:
                print("✗ extracurricular 테이블이 존재하지 않습니다.")
        except Error as e:
            print(f"테이블 확인 오류: {e}")
            table_exists = False
        finally:
            cursor.close()
            connection.close()
        return table_exists

    # ---------------- 파싱/정규화 ----------------

    def parse_datetime(self, date_str: str) -> Optional[datetime]:
        """날짜 문자열을 datetime 객체로 변환"""
        if not date_str or date_str.strip() == "":
            return None
        s = date_str.strip()
        s = s.replace('：', ':').replace('．', '.').replace('〜', '~').replace('～', '~')

        patterns = [
            r'(\d{4})\.(\d{2})\.(\d{2})\s+(\d{2}):(\d{2}):(\d{2})',
            r'(\d{4})\.(\d{2})\.(\d{2})\s+(\d{2}):(\d{2})',
            r'(\d{4})\.(\d{2})\.(\d{2})',
        ]
        for p in patterns:
            m = re.search(p, s)
            if m:
                g = m.groups()
                y, mth, d = int(g[0]), int(g[1]), int(g[2])
                H = int(g[3]) if len(g) > 3 and g[3] else 0
                M = int(g[4]) if len(g) > 4 and g[4] else 0
                S = int(g[5]) if len(g) > 5 and g[5] else 0
                return datetime(y, mth, d, H, M, S)
        return None

    def _is_ambiguous_location_text(self, text: str) -> bool:
        for pat in AMBIGUOUS_LOCATION_PATTERNS:
            if re.search(pat, text):
                return True
        return False

    def extract_location(self, text: str) -> Optional[str]:
        """텍스트에서 장소 정보 추출 + 모호한 표현 정규화"""
        # 대면 장소
        for pattern in [r'대면\(([^)]+)\)', r'장소[:\s]*([^\n]+)', r'위치[:\s]*([^\n]+)']:
            m = re.search(pattern, text)
            if m:
                loc = m.group(1).strip()
                if self._is_ambiguous_location_text(loc):
                    return AMBIGUOUS_LOCATION_NORMALIZED
                return loc

        # 온라인 여부
        if '온라인' in text or '이캠퍼스' in text:
            return '온라인'

        # 문서 어디든 모호한 표현이 있으면 정규화
        if self._is_ambiguous_location_text(text):
            return AMBIGUOUS_LOCATION_NORMALIZED

        return None

    def extract_keywords(self, text: str) -> List[str]:
        """활동목적과 제목에서 키워드 추출"""
        keyword_patterns = {
            '창의': ['창의', '창의력', '창의성', '창의적', '창의융합'],
            '소통': ['소통', '커뮤니케이션', '의사소통'],
            '리더십': ['리더십', '리더', '지도력'],
            '문제해결': ['문제해결', '문제 해결'],
            '융합': ['융합', '통합', '다학제'],
            '협업': ['협업', '팀워크', '협력'],
            'AI': ['AI', '인공지능', 'ChatGPT', '머신러닝'],
            '데이터사이언스': ['데이터', '데이터사이언스', '빅데이터', '데이터분석'],
            '프로그래밍': ['프로그래밍', '코딩', '파이썬', 'Python'],
            '영상편집': ['영상편집', '다빈치', 'DaVinci'],
            '디자인': ['디자인', '설계', '캡스톤'],
            '진로': ['진로', '취업', '커리어'],
            '자기탐색': ['자기탐색', '자기계발', '성찰'],
            '글쓰기': ['글쓰기', '작문', '에세이', '논제'],
            '토론': ['토론', '토의', '논쟁'],
            '봉사': ['봉사', '사회봉사', '자원봉사'],
            '인권': ['인권', '인권교육', '차별'],
            '다문화': ['다문화', '글로벌', '국제'],
            '온라인학습': ['온라인', '이러닝', 'e-learning'],
            '특강': ['특강', '강의', '세미나'],
            '워크샵': ['워크샵', '실습'],
            '경진대회': ['경진대회', '공모전', '대회']
        }
        extracted = set()
        lower = text.lower()

        for cat, pats in keyword_patterns.items():
            for pat in pats:
                if pat.lower() in lower or pat in text:
                    extracted.add(cat)
                    break

        if any(w in text for w in ['공학', '엔지니어', '기술']):
            extracted.add('공학')
        if any(w in text for w in ['경영', '비즈니스']):
            extracted.add('경영')
        if any(w in text for w in ['마일리지', '포인트', '적립']):
            extracted.add('마일리지')
        if any(w in text for w in ['수료증', '인증']):
            extracted.add('수료증')
        if '1학년' in text and '대상' in text:
            extracted.add('신입생')

        return list(extracted)

    # -------------- 파싱/적재 파이프라인 --------------

    def parse_single_item(self, item_text: str) -> Dict[str, Any]:
        """단일 비교과 활동 데이터 파싱"""
        lines = item_text.strip().split('\n')
        data = {
            # 비교과 고유아이디가 JSON에 있으면 채우고 없으면 None
            'extracurricular_id': None,
            'title': '',
            'url': '',
            'description': '',
            'activity_start': None,
            'activity_end': None,
            'application_start': None,
            'application_end': None,
            'keywords': [],
            'location': None
        }

        description_parts = []
        for line in lines:
            line = line.strip()

            # 고유아이디 라벨 예시: "ID:", "고유아이디:", "비교과ID:" 등 필요 시 추가
            if line.startswith(('ID:', '고유아이디:', '비교과ID:')):
                val = line.split(':', 1)[1].strip()
                if val.isdigit():
                    data['extracurricular_id'] = int(val)

            elif line.startswith('제목:'):
                data['title'] = line.replace('제목:', '').strip()

            elif line.startswith('URL:'):
                data['url'] = line.replace('URL:', '').strip()

            elif line.startswith('신청기간:'):
                period = line.split('신청기간:', 1)[1].strip().replace('〜','~').replace('～','~')
                if '~' in period:
                    start_str, end_str = [s.strip() for s in period.split('~', 1)]
                    data['application_start'] = self.parse_datetime(start_str)
                    data['application_end'] = self.parse_datetime(end_str)

            elif line.startswith('진행기간:'):
                period = line.split('진행기간:', 1)[1].strip().replace('〜','~').replace('～','~')
                if '~' in period:
                    start_str, end_str = [s.strip() for s in period.split('~', 1)]
                    data['activity_start'] = self.parse_datetime(start_str)
                    data['activity_end'] = self.parse_datetime(end_str)

            elif any(keyword in line for keyword in ['활동목적:', '참여혜택', '진행절차:', '운영방식:']):
                description_parts.append(line)

            elif line and not any(line.startswith(prefix) for prefix in
                                  ['Unnamed:', '제목:', 'URL:', '신청기간:', '진행기간:', '대상자:', '선정방법:', 'ID:', '고유아이디:', '비교과ID:']):
                description_parts.append(line)

        data['description'] = '\n'.join(description_parts)
        keyword_text = f"{data['title']} {data['description']}"
        data['keywords'] = self.extract_keywords(keyword_text)
        data['location'] = self.extract_location(item_text)

        return data

    def insert_data(self, data: Dict[str, Any]) -> Optional[int]:
        """새 데이터 삽입 (중복 체크 후 INSERT) -> 반환: 비교과 고유아이디(extracurricular_id)"""
        connection = self.get_connection()
        if not connection:
            return None
        cursor = connection.cursor()
        try:
            # 중복 체크 (제목과 URL 기준)
            cursor.execute("""
                SELECT extracurricular_id FROM extracurricular 
                WHERE title = %s AND url = %s AND is_deleted = 0
            """, (data['title'], data['url']))
            
            existing = cursor.fetchone()
            if existing:
                print(f"중복 데이터 스킵: {data['title']} (extracurricular_id: {existing[0] or 'NULL'})")
                return existing[0]

            # 1) 우선 레코드 생성 (extracurricular_id는 주어지면 포함, 아니면 NULL)
            sql = """
            INSERT INTO extracurricular (
                extracurricular_id,
                title, url, description,
                activity_start, activity_end, application_start, application_end,
                keywords, location
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                data.get('extracurricular_id'),
                data['title'],
                data['url'],
                data['description'],
                data['activity_start'],
                data['activity_end'],
                data['application_start'],
                data['application_end'],
                json.dumps(data['keywords'], ensure_ascii=False) if data['keywords'] else None,
                data['location']
            ))
            connection.commit()

            # 방금 생성된 PK
            new_pk = cursor.lastrowid

            # 2) 고유아이디가 없었다면, PK로 채운 뒤 그 값을 최종 ID로 사용
            final_ext_id = data.get('extracurricular_id')
            if final_ext_id is None:
                cursor.execute("""
                    UPDATE extracurricular
                    SET extracurricular_id = %s
                    WHERE extracurricular_pk_id = %s
                """, (new_pk, new_pk))
                connection.commit()
                final_ext_id = new_pk

            # 로그: PK와 고유아이디 모두 출력
            print(f"저장 완료 - PK: {new_pk}, extracurricular_id(고유): {final_ext_id}, 제목: {data['title']}")
            return final_ext_id

        except Error as e:
            print(f"데이터 INSERT 오류: {e}")
            connection.rollback()
            return None
        finally:
            cursor.close()
            connection.close()

    def load_json_file(self, file_path: str) -> List[Dict[str, str]]:
        """JSON 파일 로드"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"파일 로드 완료: {file_path} ({len(data)}개 항목)")
                return data
        except Exception as e:
            print(f"파일 로드 중 오류 발생 {file_path}: {e}")
            return []

    def process_multiple_files(self, file_paths: List[str]):
        """여러 JSON 파일 처리 (INSERT)"""
        total_processed = 0
        for file_path in file_paths:
            if not os.path.exists(file_path):
                print(f"파일을 찾을 수 없습니다: {file_path}")
                continue

            print(f"\n=== {file_path} 처리 시작 ===")
            data = self.load_json_file(file_path)
            if data:
                processed_count = 0
                for item in data:
                    try:
                        # item 구조가 {"text": "..."} 라고 가정
                        parsed_data = self.parse_single_item(item['text'])
                        if parsed_data['title']:
                            ext_id = self.insert_data(parsed_data)
                            if ext_id is not None:
                                keywords_str = ', '.join(parsed_data['keywords']) if parsed_data['keywords'] else '없음'
                                print(f"  키워드: {keywords_str}")
                                print(f"  위치: {parsed_data['location'] or '미기재'}")
                                processed_count += 1
                            else:
                                print(f"저장 실패: {parsed_data['title']}")
                        else:
                            print(f"제목이 없는 데이터 스킵: {item['text'][:50]}...")
                    except Exception as e:
                        print(f"데이터 처리 중 오류: {e}")
                        print(f"문제 데이터: {item['text'][:120]}...")
                print(f"{file_path}에서 {processed_count}개 항목 처리 완료")
                total_processed += processed_count
        print(f"\n=== 전체 처리 완료: 총 {total_processed}개 항목 ===")
        return total_processed

    def check_duplicate_prevention(self):
        """중복 방지 확인"""
        connection = self.get_connection()
        if not connection:
            return
        cursor = connection.cursor()
        try:
            cursor.execute("""
                SELECT title, COUNT(*) as cnt 
                FROM extracurricular 
                WHERE is_deleted = 0 
                GROUP BY title 
                HAVING cnt > 1
                ORDER BY cnt DESC
            """)
            duplicates = cursor.fetchall()
            
            if duplicates:
                print(f"\n중복된 제목 발견: {len(duplicates)}개")
                for title, count in duplicates[:10]:  # 상위 10개만 출력
                    print(f"  '{title}': {count}개")
            else:
                print("✓ 중복된 제목이 없습니다.")
                
        except Error as e:
            print(f"중복 확인 오류: {e}")
        finally:
            cursor.close()
            connection.close()

# -------------------- 실행 스크립트 --------------------

if __name__ == "__main__":
    # RDS 연결 설정
    db_config = {
        'host': '127.0.0.1',
        'database': 'test',  # 실제 존재하는 DB명으로 교체
        'user': 'root',
        'password': '1234',
        'port': 3306
    }

    parser = ExtracurricularParser(db_config)

    print("=== 기존 테이블 삭제 후 재생성 ===")
    # 강제로 테이블 삭제 후 재생성하려면 force_drop=True
    if parser.drop_and_recreate_table(force_drop=True):  # 또는 force_drop=False로 사용자 확인
        
        print("\n=== JSON 파일 처리 시작 ===")
        file_paths = [
            "app/data/my_csv_folder/se_wein_취창업비교과_정보(신청가능).json",
            "app/data/my_csv_folder/se_wein_일반비교과_정보(신청가능).json"
        ]

        existing_files = [p for p in file_paths if os.path.exists(p)]
        if existing_files:
            parser.process_multiple_files(existing_files)
            print("\n=== 최종 결과 확인 ===")
            parser.check_duplicate_prevention()  # 중복 확인
        else:
            print("처리할 JSON 파일이 없습니다.")
    else:
        print("테이블 재생성에 실패했습니다.")
