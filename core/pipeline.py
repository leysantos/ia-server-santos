from config.settings import USE_INTENT_LAYER
from core.dispatcher import dispatch
from core.intent_layer import analyze_intent, execute_intent
from core.router import route
from memory.rag_engine import RAGEngine, get_rag_engine


def process_request(text: str, use_rag: bool = True, rag_engine: RAGEngine = None) -> dict:
    """
    Pipeline completo: intent layer (v2) ou route → RAG → dispatch.
    """
    if USE_INTENT_LAYER:
        analysis = analyze_intent(text)
        return execute_intent(analysis, use_rag=use_rag, persist=False)

    route_result = route(text)

    if use_rag:
        engine = rag_engine or get_rag_engine()
        route_result = engine.enrich_route_result(route_result)

    return dispatch(route_result)
