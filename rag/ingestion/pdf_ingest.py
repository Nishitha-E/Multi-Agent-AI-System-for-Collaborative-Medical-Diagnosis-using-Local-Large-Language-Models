import os
import time
import hashlib
import argparse
import fitz
import chromadb
from langchain_ollama import OllamaEmbeddings

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(APP_DIR, "data")
SOURCES_DIR = os.path.join(DATA_DIR, "sources")

CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", os.path.join(DATA_DIR, "chroma_db"))
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "aegis_medical_kb")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

PDF_CHUNK_WORDS = int(os.getenv("INGEST_CHUNK_WORDS", "500"))
PDF_CHUNK_OVERLAP = int(os.getenv("INGEST_CHUNK_OVERLAP", "100"))
EMBED_BATCH_SIZE = int(os.getenv("INGEST_EMBED_BATCH", "64"))

SOURCES = {
    "gale": {
        "path": os.path.join(SOURCES_DIR, "gale_encyclopedia_of_medicine.pdf"),
        "category": "Gale Encyclopedia of Medicine"
    },
    "who_imai": {
        "path": os.path.join(SOURCES_DIR, "WHO_IMAI.pdf"),
        "category": "WHO IMAI District Clinician Manual"
    }
}


def chunk_words(text: str, chunk_size: int, overlap: int) -> list:
    words = text.split()

    if not words:
        return []

    if len(words) <= chunk_size:
        return [" ".join(words)]

    step = max(1, chunk_size - overlap)

    return [
        " ".join(words[i:i + chunk_size])
        for i in range(0, len(words), step)
        if words[i:i + chunk_size]
    ]


def _stable_id(*parts) -> str:
    return hashlib.sha1(
        "::".join(map(str, parts)).encode()
    ).hexdigest()[:20]


def iter_pdf_chunks(pdf_path: str, category: str):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Clinical source not found: {pdf_path}")

    title = os.path.splitext(
        os.path.basename(pdf_path)
    )[0].replace("_", " ").title()

    doc = fitz.open(pdf_path)

    try:
        pages = []

        for page_num, page in enumerate(doc):
            text = (page.get_text("text") or "").strip()

            if text:
                pages.append((page_num, text))

        full_text = "\n\n".join(
            f"[PAGE {page_num + 1}]\n{text}"
            for page_num, text in pages
        )

        chunks = chunk_words(
            full_text,
            PDF_CHUNK_WORDS,
            PDF_CHUNK_OVERLAP
        )

        for c_idx, chunk in enumerate(chunks):
            page_numbers = []

            for page_num, _ in pages:
                if f"[PAGE {page_num + 1}]" in chunk:
                    page_numbers.append(page_num + 1)

            page = page_numbers[0] if page_numbers else 0

            yield _stable_id(
                category,
                c_idx,
                chunk[:100]
            ), chunk, {
                "doc_id": os.path.basename(pdf_path),
                "category": category,
                "title": title,
                "source": os.path.basename(pdf_path),
                "page": page,
                "chunk": c_idx
            }

    finally:
        doc.close()


def get_chroma_collection(reset: bool = False):
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

    return client.get_or_create_collection(
        COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )


def _existing_ids(collection) -> set:
    try:
        return set(collection.get(include=[])["ids"])
    except Exception:
        return set(collection.get()["ids"])


def embed_and_upsert(
    collection,
    embedder,
    batch: list,
    existing_ids: set
) -> int:

    fresh = [
        item for item in batch
        if item[0] not in existing_ids
    ]

    if not fresh:
        return 0

    added = 0

    for start in range(0, len(fresh), EMBED_BATCH_SIZE):
        sub = fresh[start:start + EMBED_BATCH_SIZE]

        ids = [x[0] for x in sub]
        texts = [x[1] for x in sub]
        metas = [x[2] for x in sub]

        vectors = embedder.embed_documents(texts)

        collection.upsert(
            ids=ids,
            embeddings=vectors,
            documents=texts,
            metadatas=metas
        )

        existing_ids.update(ids)
        added += len(sub)

    return added


def run_ingestion(
    rebuild: bool = False,
    only: str = None,
    max_chunks: int = None
):
    print(
        f"Chroma dir: {CHROMA_DIR} | "
        f"Collection: {COLLECTION_NAME} | "
        f"Model: {OLLAMA_EMBED_MODEL}"
    )

    embedder = OllamaEmbeddings(
        model=OLLAMA_EMBED_MODEL,
        base_url=OLLAMA_BASE_URL
    )

    collection = get_chroma_collection(reset=rebuild)

    existing_ids = set() if rebuild else _existing_ids(collection)

    print(f"Already embedded: {len(existing_ids)} chunks\n")

    jobs = []

    if only in (None, "all", "gale"):
        jobs.append(
            (
                "gale",
                iter_pdf_chunks(
                    SOURCES["gale"]["path"],
                    SOURCES["gale"]["category"]
                )
            )
        )

    if only in (None, "all", "who_imai"):
        jobs.append(
            (
                "who_imai",
                iter_pdf_chunks(
                    SOURCES["who_imai"]["path"],
                    SOURCES["who_imai"]["category"]
                )
            )
        )

    grand_total = 0

    for name, generator in jobs:
        t0 = time.time()
        buf = []
        source_total = 0
        source_seen = 0

        for item in generator:
            buf.append(item)
            source_seen += 1

            if max_chunks and source_seen >= max_chunks:
                break

            if len(buf) >= 500:
                source_total += embed_and_upsert(
                    collection,
                    embedder,
                    buf,
                    existing_ids
                )
                buf = []

                print(
                    f"[{name}] embedded so far: "
                    f"{source_total} "
                    f"(elapsed {time.time() - t0:.0f}s)"
                )

        if buf:
            source_total += embed_and_upsert(
                collection,
                embedder,
                buf,
                existing_ids
            )

        grand_total += source_total

        print(
            f"[{name}] done: +{source_total} new chunks "
            f"in {time.time() - t0:.0f}s\n"
        )

    print(
        f"Total new chunks embedded: {grand_total} | "
        f"Total collection size: {collection.count()}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--rebuild",
        action="store_true"
    )

    parser.add_argument(
        "--only",
        choices=["gale", "who_imai", "all"],
        default="all"
    )

    parser.add_argument(
        "--max-chunks",
        type=int,
        default=None
    )

    args = parser.parse_args()

    run_ingestion(
        rebuild=args.rebuild,
        only=args.only,
        max_chunks=args.max_chunks
    )