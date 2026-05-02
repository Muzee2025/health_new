import os
import glob
from langchain_community.document_loaders import TextLoader, UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

# 目录配置
DOCS_DIR = "./psychology_docs"
CHROMA_DIR = "./chroma_psychology"

def get_embeddings():
    """
    配置嵌入模型：用户可根据需要选择 OpenAI 的 text-embedding-3-small
    或智谱的 embedding-2。此处默认提供 OpenAI 方式配置。
    若使用智谱，可取消下面 ZhipuAIEmbeddings 的注释并安装相应依赖。
    """
    # 从环境变量读取 API KEY，若无则使用占位符（运行前需配置）
    openai_api_key = os.getenv("OPENAI_API_KEY", "your-openai-api-key")
    
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=openai_api_key
    )

    # 若使用智谱 Embedding:
    # from langchain_community.embeddings import ZhipuAIEmbeddings
    # return ZhipuAIEmbeddings(api_key=os.getenv("ZHIPUAI_API_KEY", "your-zhipu-api-key"))

def load_documents():
    docs = []
    if not os.path.exists(DOCS_DIR):
        os.makedirs(DOCS_DIR)
        print(f"创建了文档目录 {DOCS_DIR}，请在此放入 .txt 或 .md 文件作为心理学知识源。")
        return docs

    print(f"正在扫描 {DOCS_DIR} 下的文档...")
    for ext in ("*.txt", "*.md"):
        for filepath in glob.glob(os.path.join(DOCS_DIR, ext)):
            try:
                if filepath.endswith(".txt"):
                    loader = TextLoader(filepath, encoding="utf-8")
                elif filepath.endswith(".md"):
                    loader = UnstructuredMarkdownLoader(filepath)
                
                loaded_docs = loader.load()
                docs.extend(loaded_docs)
                print(f"已加载: {filepath} ({len(loaded_docs)} 个文档)")
            except Exception as e:
                print(f"加载 {filepath} 失败: {e}")
    return docs

def main():
    print("=== 开始构建心理学 RAG 知识库 ===")
    documents = load_documents()
    if not documents:
        print("未找到任何文档。请在 ./psychology_docs/ 目录下添加心理咨询伦理、倾听技术、CBT 基础、危机干预话术、情绪调节方法等内容的 .txt 或 .md 文件后重试。")
        return

    # 使用 RecursiveCharacterTextSplitter 按 500 字符分块
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", "。", "！", "？", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)
    print(f"文档切分为 {len(chunks)} 个知识片段。")

    # 获取嵌入模型
    embeddings = get_embeddings()

    print(f"正在生成向量并存入持久化目录 {CHROMA_DIR} ...")
    # 存入 ChromaDB 进行持久化
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DIR
    )
    
    print("构建完成！知识库已成功保存。您现在可以运行 rag_module.py 进行测试。")

if __name__ == "__main__":
    main()
