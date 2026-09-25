"""Semantic search over posting text. Used by ask.py as the search_postings tool."""
import chromadb
from chromadb.utils import embedding_functions
from index import EMBED_MODEL

_collection = None


def _get_collection():
    global _collection
    if _collection is None:  # load the model once, on first search
        client = chromadb.PersistentClient(path="chroma_db")
        embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
        _collection = client.get_collection("postings", embedding_function=embed_fn)
    return _collection


def search_postings(text, k=8, job_ids=None):
    """Return the k chunks closest in meaning to text, optionally only from certain jobs."""
    where = {"job_id": {"$in": job_ids}} if job_ids else None
    res = _get_collection().query(query_texts=[text], n_results=k, where=where)
    return [
        {
            "job_id": meta["job_id"],
            "job_title": meta["job_title"],
            "company": meta["company"],
            "text": doc,
            "similarity": round(1 - dist, 3),
        }
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
    ]


if __name__ == "__main__":
    for r in search_postings(input("Search: ")):
        print(f"\n[{r['similarity']}] {r['job_title']} - {r['company']} (job {r['job_id']})\n{r['text']}")
