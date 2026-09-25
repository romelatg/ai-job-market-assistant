"""Builds the search index: splits every posting into chunks, embeds them, stores them in ChromaDB.
Run it again whenever you add new postings (it rebuilds the index from scratch)."""
import chromadb
from chromadb.utils import embedding_functions
from db import get_connection

EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"  # understands Spanish and English
MAX_CHARS = 400  # the model only reads ~128 tokens per chunk, so keep chunks short


def chunk_text(text, max_chars=MAX_CHARS):
    """Split a posting into chunks of up to max_chars, breaking on line breaks and spaces."""
    paragraphs = [p.strip() for p in text.replace("\r", "").split("\n") if p.strip()]
    pieces = []
    for p in paragraphs:
        while len(p) > max_chars:  # split very long paragraphs at a space
            cut = p.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            pieces.append(p[:cut].strip())
            p = p[cut:].strip()
        if p:
            pieces.append(p)

    chunks, current = [], ""
    for piece in pieces:  # merge small pieces so chunks aren't tiny
        if current and len(current) + len(piece) + 1 > max_chars:
            chunks.append(current)
            current = piece
        else:
            current = (current + "\n" + piece).strip()
    if current:
        chunks.append(current)
    return chunks


def main():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT job_id, job_title, company, description FROM dbo.jobs")
    jobs = cursor.fetchall()
    conn.close()

    client = chromadb.PersistentClient(path="chroma_db")
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    try:
        client.delete_collection("postings")
    except Exception:
        pass
    collection = client.create_collection(
        "postings", embedding_function=embed_fn, metadata={"hnsw:space": "cosine"}
    )

    ids, docs, metas = [], [], []
    for job_id, title, company, description in jobs:
        for i, chunk in enumerate(chunk_text(description or "")):
            ids.append(f"{job_id}-{i}")
            docs.append(chunk)
            metas.append({"job_id": job_id, "job_title": title or "", "company": company or ""})

    collection.add(ids=ids, documents=docs, metadatas=metas)
    print(f"Indexed {len(jobs)} postings as {len(docs)} chunks.")


if __name__ == "__main__":
    main()
