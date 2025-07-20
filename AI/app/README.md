# RAG_Agent 프로젝트

이 프로젝트는 사용자 맞춤형 비교과 활동을 추천하고, 해당 활동에 대한 질문에 자연어로 응답할 수 있는 **Agentic RAG 기반 챗봇 시스템**을 구현합니다. LangChain 프레임워크를 활용해 다양한 도구를 사용하는 LLM Agent를 구성하며, 사용자의 관심사와 시간표를 고려하여 활동을 필터링하고 추천합니다.

---

## 프로젝트 구조

```
RAG_Agent/
└── AI/
    ├── app/
    │   ├── chatbot/
    │   │   └── Agent_Rag_Chatbot.py      # 메인 챗봇 로직 (RAG Agent)
    │   ├── data/
    │   │   ├── users.json                # 사용자 프로필 정보
    │   │   └── my_csv_folder/
    │   │       ├── se_wein_일반비교과_정보(신청가능).json
    │   │       └── se_wein_취창업비교과_정보(신청가능).json
    │   └── agent_RAG_requirement.txt     # 패키지 설치 목록
    └── README.md                         # (이 파일)
```

---

## 핵심 기능

- **비교과 활동 Top-5 추천**  
  사용자 질의와 활동 제목의 임베딩 유사도(80%) + 사용자 관심사와의 유사도(20%) 기반 점수 계산

- **시간표 충돌 자동 필터링**  
  사용자 `timetable` 정보 기반으로 겹치는 활동 제거

- **자연어 질의 응답**  
  "1번 신청기간 알려줘", "그건 어디서 열려?"처럼 프로그램 이름을 암시하는 질문에도 정확하게 대응

- **LangChain Agent 구성**  
  LangChain의 `Tool`, `initialize_agent`, `OPENAI_FUNCTIONS` 에이전트를 사용해 RAG 기반 질의 추론

---

## 실행 방법

```bash
cd AI/app/chatbot/
python Agent_Rag_Chatbot.py
```

실행 시 사용자 이름을 입력한 후 챗봇과 상호작용할 수 있습니다.

예시:

```
사용자 이름을 입력하세요: 조은영
궁금한 내용을 입력하세요 ('종료' 입력 시 종료): AI 관련 비교과 뭐 있어?
→ Top-5 추천

궁금한 내용을 입력하세요: 1번 신청기간 알려줘
→ 해당 활동 내용 기반 GPT 응답
```

---

## API 키 설정

노션 AI 파트에 API키가 적혀있습니다.
아래 두 코드의 Notion_API_KEY를 지우고 노션의 API 코드를 복사해서 붙여넣기 해주세요
아래 두 코드는 17,18번째에 위치해 있습니다.

lient = OpenAI(api_key="Notion_API_KEY")
llm = ChatOpenAI(openai_api_key="Notion_API_KEY", temperature=0)
---

## 의존성 설치

아래 명령어로 필요한 패키지를 설치하세요:

```bash
pip install -r app/agent_RAG_requirement.txt
```

---

## 주요 구성요소 설명

| 구성 요소 | 설명 |
|-----------|------|
| `users.json` | 사용자 이름, 관심사, 시간표 정보를 담은 JSON 파일 |
| 활동 JSON | 비교과 활동의 상세 설명 포함, 추천 및 질의 응답 대상 |
| `get_embedding` | 제목/관심사/질문 임베딩 계산 |
| `search_top5_programs_with_explanation` | 필터링 + 점수화된 추천 결과 출력 |
| `answer_program_question_by_title` | 제목 유사도 기반 GPT 질의 응답 |
| `LangChain Agent` | 위 함수들을 도구로 등록해 GPT가 적절히 선택하여 실행 |

---

## 활용 예시

- 사용자 관심사와 질문 기반 활동 추천
- 활동 시간표 중복 제거
- 사용자 질문의 맥락을 이해하고 자연어로 응답

이 시스템은 비교과 활동 추천 챗봇의 MVP 형태이며, 추후 웹 연동 및 다중 사용자 대응 기능으로 확장 가능합니다.