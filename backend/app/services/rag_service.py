import os
import chromadb
from chromadb.utils import embedding_functions

# Initialize ChromaDB client
CHROMA_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "chroma_db")
client = chromadb.PersistentClient(path=CHROMA_DB_DIR)

# We use the default ONNX MiniLM embedding function
embedding_function = embedding_functions.DefaultEmbeddingFunction()

# Get or create collection
collection = client.get_or_create_collection(
    name="health_knowledge",
    embedding_function=embedding_function
)

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into chunks with overlap."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def add_document_to_rag(doc_id: int, title: str, content: str):
    """Add a document to ChromaDB, chunking it first."""
    chunks = chunk_text(content)
    if not chunks:
        return
    
    ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [{"doc_id": doc_id, "title": title, "chunk_index": i} for i in range(len(chunks))]
    
    collection.add(
        documents=chunks,
        metadatas=metadatas,
        ids=ids
    )

def delete_document_from_rag(doc_id: int):
    """Delete all chunks of a document from ChromaDB."""
    # Since ChromaDB doesn't support deleting by partial id directly easily in older versions,
    # we can query by metadata to find ids to delete.
    results = collection.get(where={"doc_id": doc_id})
    if results and results['ids']:
        collection.delete(ids=results['ids'])

def query_rag(query: str, n_results: int = 3) -> str:
    """Query the knowledge base and return concatenated relevant text."""
    if collection.count() == 0:
        return ""
        
    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, collection.count())
    )
    
    if not results['documents'] or not results['documents'][0]:
        return ""
        
    # Concatenate the retrieved chunks
    retrieved_texts = []
    for i, doc in enumerate(results['documents'][0]):
        title = results['metadatas'][0][i].get('title', '知识库')
        retrieved_texts.append(f"【{title}】片段:\n{doc}")
        
    return "\n\n".join(retrieved_texts)
