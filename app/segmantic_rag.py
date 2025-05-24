# semantic_rag.py

from llmware.library import Library
from llmware.retrieval import Query
from llmware.models import ModelCatalog

def semantic_rag(library_name, llm_model_name):
    """ Semantic Query 기반 RAG 성능 향상 함수 """

    lib = Library().load_library(library_name)
    query_engine = Query(lib)
    model = ModelCatalog().load_model(llm_model_name)

    print("\n RAG 챗봇 (Semantic Query 강화) 에 오신 걸 환영합니다!")
    print("종료하려면 'exit' 입력\n")

    while True:
        user_question = input(" 질문: ")

        if user_question.lower() in ["exit", "quit", "종료"]:
            print("챗봇을 종료합니다.")
            break

        # 1. Semantic Query로 많은 결과를 뽑음
        search_results = query_engine.semantic_query(user_question, result_count=50)

        if not search_results:
            print(" 관련 정보를 찾지 못했습니다.\n")
            continue

        # 2. 문서별로 그룹핑
        doc_to_results = {}
        for res in search_results:
            doc_name = res.get("file_source", "unknown")
            doc_to_results.setdefault(doc_name, []).append(res)

        # 3. 문서별 상위 결과만 모아서 context 생성
        combined_context = ""
        for doc, results in doc_to_results.items():
            top_results = results[:3]
            combined_text = " ".join([r["text"] for r in top_results])
            combined_context += combined_text + "\n"

        # 4. 모델에 질문 + 문맥 기반 답변 생성
        response = model.inference(user_question, add_context=combined_context)

        print("\n 답변:", response, "\n")

