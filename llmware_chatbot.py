# llmware RAG 챗봇 
# ========== 1. 라이브러리 생성 및 csv 파일 파싱 ==========
from llmware.library import Library
from llmware.retrieval import Query
from llmware.models import ModelCatalog
from llmware.setup import Setup
from llmware.configs import LLMWareConfig, MilvusConfig
from llmware.prompts import Prompt
import os

def prepare_library(library_name="my_library", document_folder="my_csv_folder"):
    """ 라이브러리 생성 + 폴더 안 csv 파일 파싱하는 함수 """
    # DB 설정
    LLMWareConfig().set_active_db("sqlite")
    
    ingestion_folder_path = document_folder
    
    # 라이브러리 생성
    library = Library().create_new_library(library_name)
    print(f" 라이브러리 '{library_name}' 생성 완료.")

    # 폴더 안 파일들 추가
    parsing_output = library.add_files(ingestion_folder_path)
    print(f" CSV 파싱 완료: {parsing_output}")

    return library

# ========== 2. 라이브러리에 임베딩 적용 ==========
def install_embeddings(library, embedding_model="mini-lm-sbert"):
    """ 라이브러리에 임베딩 설치하는 함수 """
    # 벡터 DB 설정
    MilvusConfig().set_config("lite", True)
    LLMWareConfig().set_vector_db("chromadb")

    print(f" 벡터 임베딩 시작 - 모델: {embedding_model}")
    library.install_new_embedding(embedding_model_name=embedding_model, vector_db="chromadb", batch_size=100)
    print(" 벡터 임베딩 완료.")

# ========== 3. 챗봇 메인 루프 ==========
def start_chatbot(library_name, model_name="bling-answer-tool"):
    """ RAG 챗봇 실행 함수 """

    # 라이브러리와 모델 로드
    lib = Library().load_library(library_name)
    query_engine = Query(lib)
    model = ModelCatalog().load_model(model_name)

    print("\n RAG 챗봇에 오신 걸 환영합니다!")
    print("종료하려면 'exit' 입력\n")

    while True:
        user_question = input(" 질문: ")

        if user_question.lower() in ["exit", "quit", "종료"]:
            print("챗봇을 종료합니다.")
            break

        # semantic query를 통해 유사 문장 검색
        search_results = query_engine.semantic_query(user_question, result_count=3)

        if not search_results:
            print(" 관련 정보를 찾지 못했습니다.\n")
            continue

        # 검색된 상위 3개 문장을 문맥으로 합치기
        combined_context = " ".join([res["text"] for res in search_results])

        # 모델로 질문 + 문맥 기반 답변 생성
        response = model.inference(user_question, add_context=combined_context)

        print("\n 답변:", response, "\n")

# ========== 4. 전체 실행 ==========
if __name__ == "__main__":
    library_name = "my_library"  # 원하는 이름
    document_folder =  "my_csv_folder"  # 폴더 이름으로 수정
    embedding_model = "mini-lm-sbert"  # 사용할 임베딩 모델
    llm_model_name = "bling-answer-tool"  # 사용할 LLM 모델

    # 1단계: 라이브러리 생성 및 문서 파싱
    library = prepare_library(library_name, document_folder)

    # 2단계: 벡터 임베딩 생성
    install_embeddings(library, embedding_model)

    # 3단계: 챗봇 실행
    start_chatbot(library_name, llm_model_name)
