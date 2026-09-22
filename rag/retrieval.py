import os, chromadb
from langchain_ollama import OllamaEmbeddings

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", os.path.join(APP_DIR, "data", "chroma_db"))
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "aegis_medical_kb")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")


class VectorRAG:
    def __init__(self, persist_dir: str = CHROMA_DIR, collection_name: str = CHROMA_COLLECTION):
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_collection(collection_name)

        if self._collection.count() == 0:
            raise RuntimeError(
                f"Chroma collection '{collection_name}' is empty. "
                f"Run the ingestion pipeline first."
            )

        self._embedder = OllamaEmbeddings(
            model=OLLAMA_EMBED_MODEL,
            base_url=OLLAMA_BASE_URL
        )

    def retrieve(self, query: str, top_k: int = 6, min_similarity: float = 0.25) -> list:
        q = self._embedder.embed_query(query)
        n = max(top_k * 10, 30)

        res = self._collection.query(
            query_embeddings=[q],
            n_results=n
        )

        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]

        results = []
        seen = set()

        for _id, text, meta, dist in zip(ids, docs, metas, dists):
            meta = meta or {}

            score = 1.0 / (1.0 + dist) if dist is not None else 0.0

            if score < min_similarity:
                continue

            chunk_id = _id

            if chunk_id in seen:
                continue

            seen.add(chunk_id)

            results.append({
                "doc_id": meta.get("doc_id", _id),
                "category": meta.get("category", "Reference"),
                "title": meta.get("title", meta.get("doc_id", _id)),
                "source": meta.get("source", ""),
                "page": meta.get("page", ""),
                "text": text,
                "score": round(score, 4)
            })

        results.sort(key=lambda x: x["score"], reverse=True)

        return results[:top_k]


_rag_instance = None


def get_rag():
    global _rag_instance

    if _rag_instance is None:
        _rag_instance = VectorRAG()
        print("[retrieval] Using Chroma VectorRAG with Ollama embeddings")

    return _rag_instance