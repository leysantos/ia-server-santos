from memory.embeddings import NomicEmbedder, _MAX_EMBED_WORDS


def test_truncate_limits_words_before_chars():
    long = " ".join(f"w{i}" for i in range(_MAX_EMBED_WORDS + 200))
    out = NomicEmbedder._truncate(long)
    assert len(out.split()) == _MAX_EMBED_WORDS


def test_truncate_short_text_unchanged():
    text = "Decreto municipal de segurança contra incêndio."
    assert NomicEmbedder._truncate(text) == text
