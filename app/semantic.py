"""Real multilingual E5 embeddings; PostgreSQL is the only application index."""

import os
from functools import lru_cache

from sqlalchemy import text

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


@lru_cache(maxsize=1)
def encoder():
    from fastembed import TextEmbedding

    return TextEmbedding(
        MODEL,
        cache_dir=os.getenv("EMBEDDING_CACHE_DIR", "/opt/embedding-models"),
        threads=2,
        local_files_only=os.getenv("EMBEDDING_OFFLINE", "true") == "true",
    )


def chunks(value, size=180, overlap=40):
    words = value.split()
    return [" ".join(words[i : i + size]) for i in range(0, len(words), size - overlap)]


def vector(value):
    return "[" + ",".join(str(float(v)) for v in value) + "]"


def index_document(session, source_type, source_id, value):
    parts = chunks(value)
    session.execute(
        text("DELETE FROM semantic_chunks WHERE source_type=:kind AND source_id=:id"),
        {"kind": source_type, "id": source_id},
    )
    for index, (part, embedding) in enumerate(zip(parts, encoder().embed(["" + p for p in parts]))):
        session.execute(
            text("""INSERT INTO semantic_chunks(source_type,source_id,chunk_index,text,model,embedding)
            VALUES(:kind,:id,:index,:text,:model,CAST(:embedding AS vector))"""),
            {
                "kind": source_type,
                "id": source_id,
                "index": index,
                "text": part,
                "model": MODEL,
                "embedding": vector(embedding),
            },
        )
    return len(parts)


def search(session, query, source_type=None, limit=20):
    embedding = next(encoder().embed(["" + query]))
    rows = session.execute(
        text("""SELECT source_type,source_id,chunk_index,text,model,
        1-(embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM semantic_chunks WHERE model=:model AND (CAST(:kind AS text) IS NULL OR source_type=CAST(:kind AS text))
        ORDER BY embedding <=> CAST(:embedding AS vector) LIMIT :limit"""),
        {"embedding": vector(embedding), "model": MODEL, "kind": source_type, "limit": limit},
    )
    return [dict(r._mapping) for r in rows]
