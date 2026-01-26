# build_chroma_db.py
import os
import shutil
from dotenv import load_dotenv  # 추가: .env 파일 로드 라이브러리
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

# --- 환경 변수 로드 ---
# 프로젝트 루트 폴더에 있는 .env 파일을 찾아 읽어옵니다.
load_dotenv() 

# --- 경로 설정 ---
# 현재 터미널 실행 위치가 compliance_api 폴더이므로 상대 경로를 사용합니다.
BASE_KNOWLEDGE_PATH = "resources/knowledge_base/"
VECTOR_DB_PATH = "vector_db/"

def build_vector_store():
    # 1. API 키 확인 (디버깅용)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ 에러: OPENAI_API_KEY가 설정되지 않았습니다.")
        print("💡 팁: 프로젝트 루트 폴더에 .env 파일이 있는지, 내부에 OPENAI_API_KEY=sk-... 가 정확히 작성되었는지 확인하세요.")
        return

    print(f"🔑 API 키 확인 완료: {api_key[:10]}...") # 보안을 위해 앞부분만 출력

    # 2. 기존 DB 초기화
    if os.path.exists(VECTOR_DB_PATH):
        print(f"♻️ 기존 Vector DB({VECTOR_DB_PATH})를 삭제하고 새로 구축합니다...")
        shutil.rmtree(VECTOR_DB_PATH)

    # 3. 모든 하위 폴더에서 PDF 로드
    print(f"📂 '{BASE_KNOWLEDGE_PATH}'에서 데이터를 읽어오는 중...")
    loader = DirectoryLoader(
        BASE_KNOWLEDGE_PATH, 
        glob="**/*.pdf", 
        loader_cls=PyPDFLoader,
        recursive=True
    )
    documents = loader.load()
    
    if not documents:
        print(f"⚠️ 경고: '{BASE_KNOWLEDGE_PATH}' 경로에 PDF 파일이 없습니다.")
        return

    print(f"✅ 총 {len(documents)} 페이지의 문서를 불러왔습니다.")

    # 4. 텍스트 분할 (Chunking)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120, separators=["\n\n", "\n", " ", ""])
    chunks = text_splitter.split_documents(documents)
    print(f"✂️ 문서를 {len(chunks)}개의 조각으로 나누었습니다.")

    # 5. VectorDB 생성 및 영구 저장
    print("🧠 임베딩 생성 중... (데이터 양에 따라 시간이 걸릴 수 있습니다)")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=VECTOR_DB_PATH
    )
    
    print(f"🚀 Vector DB 구축 완료! 저장 위치: {VECTOR_DB_PATH}")

if __name__ == "__main__":
    build_vector_store()