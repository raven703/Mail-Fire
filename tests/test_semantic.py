import os

import pytest

from app.semantic import chunks, encoder


def test_chunk_overlap():
    parts = chunks(" ".join(str(i) for i in range(400)))
    assert len(parts) == 3
    assert parts[0].split()[-40:] == parts[1].split()[:40]


@pytest.mark.skipif(not os.getenv("MAILFIRE_EMBEDDING_TEST"), reason="Requires real downloaded model")
def test_real_multilingual_semantics():
    import numpy as np

    vectors = list(
        encoder().embed(
            [
                "Финансовые результаты компании и годовая прибыль",
                "Annual company earnings and financial performance",
                "Рецепт приготовления супа с картофелем",
            ]
        )
    )
    assert len(vectors[0]) == 384
    assert np.dot(vectors[0], vectors[1]) > np.dot(vectors[0], vectors[2])
