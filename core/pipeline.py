from core.dispatcher import dispatch
from core.router import route
from memory.rag_engine import RAGEngine, get_rag_engine


def process_request(text: str, use_rag: bool = True, rag_engine: RAGEngine = None) -> dict:
    """
    Pipeline completo: route → RAG (opcional) → dispatch.

    Mantém compatibilidade: router e dispatcher continuam funcionando
    de forma independente quando use_rag=False.
    """
    route_result = route(text)

    if use_rag:
        engine = rag_engine or get_rag_engine()
        route_result = engine.enrich_route_result(route_result)

    return dispatch(route_result)
