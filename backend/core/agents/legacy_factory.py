"""
Registry legado de agentes simulados (BaseAgent).
Mantido para testes e rollback via USE_INTELLIGENT_AGENTS=false.
"""

from agents.arquitetura import ArquiteturaAgent
from agents.drenagem import DrenagemAgent
from agents.eletrica import EletricaAgent
from agents.estruturas import EstruturasAgent
from agents.geoprocessamento import GeoprocessamentoAgent
from agents.geotecnia import GeotecniaAgent
from agents.hidrossanitario import HidrossanitarioAgent
from agents.incendio import IncendioAgent
from agents.infraestrutura import InfraestruturaAgent
from agents.meio_ambiente import MeioAmbienteAgent
from agents.orcamento import OrcamentoAgent
from agents.saneamento import SaneamentoAgent
from agents.telecom import TelecomAgent
from agents.topografia import TopografiaAgent
from agents.transportes import TransportesAgent


def build_legacy_agents() -> dict:
    return {
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
