"""Build-time dependency weights; not mutable application storage."""

from fastembed import TextEmbedding

model = TextEmbedding(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    cache_dir="/opt/embedding-models",
    threads=2,
)
assert len(next(model.embed(["проверка модели"]))) == 384
