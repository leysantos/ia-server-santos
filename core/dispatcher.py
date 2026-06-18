from agents.arquitetura import ArquiteturaAgent
from agents.estruturas import EstruturasAgent
from agents.hidrossanitario import HidrossanitarioAgent
from agents.drenagem import DrenagemAgent
from agents.eletrica import EletricaAgent
from agents.telecom import TelecomAgent
from agents.incendio import IncendioAgent
from agents.geotecnia import GeotecniaAgent
from agents.transportes import TransportesAgent
from agents.infraestrutura import InfraestruturaAgent
from agents.saneamento import SaneamentoAgent
from agents.geoprocessamento import GeoprocessamentoAgent
from agents.topografia import TopografiaAgent
from agents.orcamento import OrcamentoAgent
from agents.meio_ambiente import MeioAmbienteAgent


# 🧠 REGISTRY CENTRAL (PADRÃO PROFISSIONAL)
AGENTS = {
    "ARQUITETURA": ArquiteturaAgent(),
    "ESTRUTURAL": EstruturasAgent(),
    "HIDROSSANITÁRIO": HidrossanitarioAgent(),
    "DRENAGEM": DrenagemAgent(),
    "ELÉTRICA": EletricaAgent(),
    "TELECOM": TelecomAgent(),
    "INCÊNDIO": IncendioAgent(),
    "GEOTECNIA": GeotecniaAgent(),
    "TRANSPORTES": TransportesAgent(),
    "INFRAESTRUTURA": InfraestruturaAgent(),
    "SANEAMENTO": SaneamentoAgent(),
    "GEOPROCESSAMENTO": GeoprocessamentoAgent(),
    "TOPOGRAFIA": TopografiaAgent(),
    "ORÇAMENTO": OrcamentoAgent(),
    "MEIO_AMBIENTE": MeioAmbienteAgent(),
}


def dispatch(route_result: dict, persist: bool = True):
    discipline = route_result.get("discipline")
    user_input = route_result.get("input")
    context = route_result.get("context")

    agent = AGENTS.get(discipline)

    if agent:
        response = agent.handle(user_input, context=context)
    else:
        response = {
            "discipline": "GERAL",
            "response": "Nenhum agente especializado encontrado para esta solicitação."
        }

    if persist:
        from core.database.service import save_agent_run

        save_agent_run(route_result=route_result, response=response)

    return response
