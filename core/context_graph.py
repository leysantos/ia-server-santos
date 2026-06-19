"""
ContextGraph — contexto compartilhado entre agentes (Orchestrator V2).

Armazena resultados por disciplina, permite consulta cruzada,
mantém histórico incremental e serialização JSON para persistência futura.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Mescla overlay sobre base (dicts recursivos, listas concatenadas)."""
    result = deepcopy(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        elif key in result and isinstance(result[key], list) and isinstance(value, list):
            result[key] = result[key] + value
        else:
            result[key] = deepcopy(value)
    return result


class ContextGraph:
    """
    Grafo de contexto compartilhado entre disciplinas de engenharia.

    nodes: último estado por disciplina
    dependencies: disciplina → disciplinas das quais depende
    history: append-only de todas as adições (histórico incremental)
    """

    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.dependencies: dict[str, list[str]] = {}
        self.history: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Escrita
    # ------------------------------------------------------------------

    def add_result(
        self,
        discipline: str,
        data: dict,
        depends_on: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Registra resultado de uma disciplina.

        Incrementa versão da disciplina e append no histórico.
        """
        discipline = discipline.strip().upper()
        depends_on = [d.strip().upper() for d in (depends_on or [])]

        if depends_on:
            self.dependencies[discipline] = list(dict.fromkeys(depends_on))

        previous = self.nodes.get(discipline, {})
        version = int(previous.get("version", 0)) + 1

        entry = {
            "discipline": discipline,
            "data": deepcopy(data),
            "depends_on": depends_on,
            "version": version,
            "timestamp": _utc_now_iso(),
        }

        self.history.append(deepcopy(entry))
        self.nodes[discipline] = entry
        return deepcopy(entry)

    def add_dependency(self, discipline: str, depends_on: list[str]) -> None:
        """Declara dependências explícitas entre disciplinas."""
        discipline = discipline.strip().upper()
        self.dependencies[discipline] = [
            d.strip().upper() for d in depends_on
        ]

    # ------------------------------------------------------------------
    # Leitura
    # ------------------------------------------------------------------

    def get(self, discipline: str) -> Optional[dict[str, Any]]:
        """Retorna o nó mais recente de uma disciplina (ou None)."""
        node = self.nodes.get(discipline.strip().upper())
        return deepcopy(node) if node else None

    def get_data(self, discipline: str) -> Optional[dict[str, Any]]:
        """Retorna apenas o payload `data` de uma disciplina."""
        node = self.get(discipline)
        return node["data"] if node else None

    def get_history(
        self,
        discipline: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Histórico incremental; filtra por disciplina se informada."""
        if discipline is None:
            return deepcopy(self.history)
        key = discipline.strip().upper()
        return [deepcopy(h) for h in self.history if h["discipline"] == key]

    def get_related(self, discipline: str) -> dict[str, dict[str, Any]]:
        """
        Consulta cruzada: disciplina + dependências declaradas
        (resultados disponíveis no grafo).
        """
        discipline = discipline.strip().upper()
        related: dict[str, dict[str, Any]] = {}

        node = self.get(discipline)
        if node:
            related[discipline] = node

        for dep in self.dependencies.get(discipline, []):
            dep_node = self.get(dep)
            if dep_node:
                related[dep] = dep_node

        return related

    def query(self, disciplines: list[str]) -> dict[str, dict[str, Any]]:
        """Consulta cruzada por lista explícita de disciplinas."""
        result: dict[str, dict[str, Any]] = {}
        for raw in disciplines:
            node = self.get(raw)
            if node:
                result[node["discipline"]] = node
        return result

    # ------------------------------------------------------------------
    # Consolidação
    # ------------------------------------------------------------------

    def merge_contexts(
        self,
        disciplines: Optional[list[str]] = None,
        other: Optional["ContextGraph"] = None,
    ) -> dict[str, Any]:
        """
        Consolida dados entre disciplinas.

        - disciplines=None → mescla todas as disciplinas do grafo atual
        - other → mescla também nós de outro ContextGraph (prioridade ao other)
        """
        merged_data: dict[str, Any] = {}
        by_discipline: dict[str, Any] = {}

        target = disciplines or list(self.nodes.keys())
        for disc in target:
            node = self.get(disc)
            if not node:
                continue
            by_discipline[disc] = node["data"]
            merged_data = _deep_merge(merged_data, node["data"])

        if other is not None:
            for disc, node in other.nodes.items():
                if disciplines and disc not in [d.strip().upper() for d in disciplines]:
                    continue
                payload = deepcopy(node.get("data", {}))
                by_discipline[disc] = _deep_merge(by_discipline.get(disc, {}), payload)
                merged_data = _deep_merge(merged_data, payload)

        return {
            "by_discipline": by_discipline,
            "merged": merged_data,
            "disciplines": sorted(by_discipline.keys()),
        }

    def build_global_context(self) -> str:
        """
        Monta contexto textual global para injeção em prompts de agentes.

        Inclui resultados por disciplina, dependências e ordem cronológica.
        """
        if not self.nodes:
            return ""

        lines = [
            "# Contexto compartilhado multidisciplinar (ContextGraph)",
            "",
            f"Disciplinas registradas: {', '.join(sorted(self.nodes.keys()))}",
            "",
        ]

        if self.dependencies:
            lines.append("## Dependências declaradas")
            for disc, deps in sorted(self.dependencies.items()):
                lines.append(f"- {disc} depende de: {', '.join(deps)}")
            lines.append("")

        lines.append("## Resultados por disciplina")
        for disc in sorted(self.nodes.keys()):
            node = self.nodes[disc]
            lines.append(f"### {disc} (v{node['version']})")
            if node.get("depends_on"):
                lines.append(f"Depende de: {', '.join(node['depends_on'])}")
            data = node.get("data", {})
            if "result" in data:
                lines.append(str(data["result"]))
            elif "summary" in data:
                lines.append(str(data["summary"]))
            else:
                lines.append(json.dumps(data, ensure_ascii=False, indent=2))
            lines.append("")

        if len(self.history) > len(self.nodes):
            lines.append("## Histórico incremental")
            for item in self.history:
                lines.append(
                    f"- [{item['timestamp']}] {item['discipline']} v{item['version']}"
                )

        return "\n".join(lines).strip()

    # ------------------------------------------------------------------
    # Serialização JSON (PostgreSQL futuro)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": deepcopy(self.nodes),
            "dependencies": deepcopy(self.dependencies),
            "history": deepcopy(self.history),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ContextGraph":
        graph = cls()
        graph.nodes = deepcopy(payload.get("nodes", {}))
        graph.dependencies = deepcopy(payload.get("dependencies", {}))
        graph.history = deepcopy(payload.get("history", []))
        return graph

    def to_json(self, **kwargs: Any) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, **kwargs)

    @classmethod
    def from_json(cls, raw: str) -> "ContextGraph":
        return cls.from_dict(json.loads(raw))

    def __repr__(self) -> str:
        return (
            f"ContextGraph(disciplines={len(self.nodes)}, "
            f"history={len(self.history)})"
        )
