import re

from config.settings import RAG_CHUNK_MAX_TOKENS, RAG_CHUNK_MIN_TOKENS


def estimate_tokens(text: str) -> int:
    """Estimativa de tokens por contagem de palavras."""
    return len(text.split())


def split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _split_long_paragraph(paragraph: str, max_tokens: int) -> list[str]:
    words = paragraph.split()
    chunks: list[str] = []
    current: list[str] = []

    for word in words:
        current.append(word)
        if len(current) >= max_tokens:
            chunks.append(" ".join(current))
            overlap = max(1, max_tokens // 10)
            current = current[-overlap:]

    if current:
        chunks.append(" ".join(current))

    return chunks


def split_text(
    text: str,
    min_tokens: int = RAG_CHUNK_MIN_TOKENS,
    max_tokens: int = RAG_CHUNK_MAX_TOKENS,
) -> list[str]:
    """
    Chunking dinâmico (600–1200 tokens) com overlap inteligente por parágrafo.
    """
    paragraphs = split_paragraphs(text)
    if not paragraphs:
        cleaned = " ".join(text.split())
        return [cleaned] if cleaned else []

    if len(paragraphs) == 1 and estimate_tokens(paragraphs[0]) <= max_tokens:
        return paragraphs

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for paragraph in paragraphs:
        para_tokens = estimate_tokens(paragraph)

        if para_tokens > max_tokens:
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_tokens = 0
            chunks.extend(_split_long_paragraph(paragraph, max_tokens))
            continue

        if current_tokens + para_tokens > max_tokens and current:
            chunks.append("\n\n".join(current))
            overlap_para = current[-1]
            current = [overlap_para]
            current_tokens = estimate_tokens(overlap_para)

        current.append(paragraph)
        current_tokens += para_tokens

        if current_tokens >= min_tokens:
            chunks.append("\n\n".join(current))
            overlap_para = current[-1]
            current = [overlap_para]
            current_tokens = estimate_tokens(overlap_para)

    if current:
        tail = "\n\n".join(current)
        if chunks and estimate_tokens(tail) < min_tokens // 3:
            chunks[-1] = f"{chunks[-1]}\n\n{tail}"
        else:
            chunks.append(tail)

    return chunks
