from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from pricing.models.price_item import PriceItem

_QUERY_STOP_WORDS = frozenset(
    {"de", "da", "do", "das", "dos", "e", "em", "para", "com", "sem", "ou", "a", "o", "na", "no", "nas", "nos"}
)

# SINAPI usa «contêiner»; usuários digitam «container».
_TERM_SYNONYMS: dict[str, str] = {
    "container": "conteiner",
    "containers": "conteiner",
}


class PriceMatcher:
    """Matching híbrido determinístico — lexical + fuzzy (sem LLM)."""

    def normalize(self, text: str) -> str:
        text = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in text if not unicodedata.combining(c))
        text = text.lower().strip()
        text = re.sub(r"[^\w\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        parts = [_TERM_SYNONYMS.get(p, p) for p in text.split()]
        return " ".join(parts)

    def lexical_hit(self, query: str, description: str) -> bool:
        q = self.normalize(query)
        d = self.normalize(description)
        if not q or not d:
            return False
        if q in d:
            return True
        tokens = [t for t in q.split() if len(t) > 2 and t not in _QUERY_STOP_WORDS]
        if not tokens:
            return False
        if len(tokens) == 1:
            return tokens[0] in d
        return all(t in d for t in tokens)

    def similarity(self, query: str, description: str) -> float:
        q = self.normalize(query)
        d = self.normalize(description)
        if not q or not d:
            return 0.0
        return SequenceMatcher(None, q, d).ratio()

    def token_overlap_score(self, query: str, description: str) -> float:
        q_tokens = {t for t in self.normalize(query).split() if len(t) > 2}
        d_tokens = {t for t in self.normalize(description).split() if len(t) > 2}
        if not q_tokens or not d_tokens:
            return 0.0
        overlap = q_tokens & d_tokens
        if not overlap:
            return 0.0
        return len(overlap) / max(len(q_tokens), 1)

    def unit_compatible(self, expected: str | None, actual: str | None) -> float:
        if not expected or not actual:
            return 0.5
        e = self.normalize(expected).replace("m2", "m²").replace("m3", "m³")
        a = self.normalize(actual).replace("m2", "m²").replace("m3", "m³")
        if e == a:
            return 1.0
        compatible = {
            ("m", "m"): 1.0,
            ("m²", "m²"): 1.0,
            ("m³", "m³"): 1.0,
            ("un", "und"): 1.0,
            ("un", "un"): 1.0,
            ("h", "hora"): 1.0,
            ("kg", "kg"): 1.0,
        }
        if (e, a) in compatible or (a, e) in compatible:
            return 1.0
        if e in ("m", "m²", "m³") and a in ("m", "m²", "m³"):
            return 0.2
        return 0.0

    _CONTRADICTIONS: tuple[tuple[frozenset[str], frozenset[str], bool], ...] = (
        (frozenset({"metalica", "metalico", "metálico", "tabuleiro", "montagem"}), frozenset({"gesso", "drywall", "dry", "parede"}), True),
        (frozenset({"mobiliz", "desmobiliz", "canteiro"}), frozenset({"sinalizador", "led", "sanitario", "assento"}), True),
        (frozenset({"topograf", "locacao"}), frozenset({"sanitario", "assento", "cavalete", "pracas"}), False),
        (frozenset({"antiderrapante", "piso"}), frozenset({"industrial", "granito", "podotatil"}), False),
        (frozenset({"sinalizacao", "placa", "acessibilidade"}), frozenset({"remocao", "remoção", "suporte"}), True),
        (frozenset({"coroamento", "concretagem", "concreto"}), frozenset({"escavacao", "escavação"}), True),
    )

    def has_contradiction(self, anchor: str, description: str) -> bool:
        a = set(self.normalize(anchor).split())
        d = set(self.normalize(description).split())
        for want, block, hard in self._CONTRADICTIONS:
            if not self._tokens_match(a, want) or not self._tokens_match(d, block):
                continue
            if hard:
                return True
            overlap = self.token_overlap_score(anchor, description)
            if overlap >= 0.25 or self.lexical_hit(anchor, description):
                continue
            return True
        return False

    def line_name_coverage(self, line_name: str, description: str) -> float:
        tokens = [t for t in self.normalize(line_name).split() if len(t) > 3]
        if not tokens:
            return 0.0
        d = self.normalize(description)
        hits = sum(1 for t in tokens if t in d)
        return hits / len(tokens)

    def accepts_match(
        self,
        line_name: str | None,
        query: str,
        description: str,
        unit: str | None = None,
        item_unit: str | None = None,
        score: float = 0.0,
    ) -> bool:
        """Só aceita composição se a descrição da base corresponder ao serviço da linha."""
        anchor = (line_name or query or "").strip()
        if not anchor or not description:
            return False
        if self.has_contradiction(anchor, description):
            return False
        if self.has_contradiction(query, description):
            return False

        ln = self.normalize(line_name) if line_name else ""
        qn = self.normalize(query) if query else ""
        dn = self.normalize(description)

        if ln and "topograf" in ln and "topograf" not in dn:
            if "gabarito" not in dn and "locacao convencional" not in dn:
                return False

        if qn and "concretagem" in qn and "concretagem" not in dn:
            return False

        if "antiderrapante" in ln and "antiderrapante" not in dn:
            return False

        if "guarda" in ln and "corpo" in ln and "cremalheira" in dn:
            return False
        if ("metalico" in ln or "metalica" in ln) and not any(
            k in dn for k in ("metalic", "metal", "aco")
        ):
            return False

        if ln and any(k in ln for k in ("sinaliz", "placa", "acessibil")):
            if "remoc" in dn and "instalac" not in dn and "fornecimento" not in dn:
                return False

        if any(k in ln for k in ("mobiliz", "desmobiliz")):
            primary = " ".join(dn.split()[:5])
            if any(k in primary for k in ("estaca", "tubulao", "broca", "raiz", "escavada")):
                return False
            exclusive_at = dn.find("exclusive")
            mobil_at = dn.find("mobiliz")
            if exclusive_at >= 0 and mobil_at > exclusive_at:
                return False
            if not any(k in dn for k in ("mobiliz", "desmobiliz", "container", "canteiro")):
                return False
        if "estaca" in ln and "estaca" not in dn:
            return False
        if "coroamento" in ln and "coroamento" not in dn:
            return False
        if ("metalica" in ln or "tabuleiro" in ln) and any(
            k in dn for k in ("tapume", "telha", "gesso", "drywall", "parede")
        ):
            return False

        name_overlap = self.token_overlap_score(line_name, description) if line_name else 0.0
        query_overlap = self.token_overlap_score(query, description) if query else 0.0
        overlap = max(name_overlap, query_overlap)
        coverage = self.line_name_coverage(line_name, description) if line_name else 0.0

        if line_name:
            sig = [
                t
                for t in self.normalize(line_name).split()
                if len(t) > 3 and t not in {"servicos", "preliminares", "acessibilidade"}
            ]
            if sig and coverage < 0.34 and not self.lexical_hit(line_name, description):
                if not (
                    query
                    and (
                        self.token_overlap_score(query, description) >= 0.35
                        or self.lexical_hit(query, description)
                    )
                ):
                    return False

        query_ok = not query or query_overlap >= 0.18 or self.lexical_hit(query, description)
        if not query_ok:
            return False

        if self.lexical_hit(line_name or query, description):
            return score >= 0.48

        if overlap >= 0.40 and score >= 0.55 and coverage >= 0.34:
            return True

        if overlap >= 0.30 and score >= 0.65 and coverage >= 0.5:
            return True

        if query and self.token_overlap_score(query, description) >= 0.5 and score >= 0.55:
            return True

        return False

    @staticmethod
    def _tokens_match(tokens: set[str], keywords: frozenset[str]) -> bool:
        for kw in keywords:
            if len(kw) >= 4 and kw in tokens:
                return True
            for t in tokens:
                if len(t) < 4 or len(kw) < 4:
                    continue
                if t.startswith(kw) or kw.startswith(t):
                    return True
        return False

    def composite_score(
        self,
        line_name: str | None,
        query: str,
        description: str,
        unit: str | None = None,
        item_unit: str | None = None,
    ) -> float:
        """Prioriza correspondência entre nome da linha PPD e descrição da base."""
        scores: list[float] = []
        if line_name:
            scores.append(self.match_score(line_name, description, unit, item_unit))
        if query:
            scores.append(self.match_score(query, description, unit, item_unit) * 0.9)
        if not scores:
            return 0.0
        return round(max(scores), 4)

    def match_score(
        self,
        query: str,
        description: str,
        unit: str | None = None,
        item_unit: str | None = None,
    ) -> float:
        fuzzy = self.similarity(query, description)
        tokens = self.token_overlap_score(query, description)
        lexical = 1.0 if self.lexical_hit(query, description) else 0.0
        unit_score = self.unit_compatible(unit, item_unit)
        combined = (0.35 * fuzzy) + (0.45 * tokens) + (0.10 * lexical) + (0.10 * unit_score)
        if tokens < 0.15 and not lexical:
            combined *= 0.5
        if unit and item_unit and unit_score < 0.3:
            generic = self.normalize(unit) in ("un", "und", "unidade")
            if not generic:
                combined *= 0.4
        return round(min(combined, 1.0), 4)

    def fuzzy_match(
        self,
        query: str,
        items: list[PriceItem],
        limit: int = 10,
        min_score: float = 0.35,
        unit: str | None = None,
    ) -> list[PriceItem]:
        scored = [
            (self.match_score(query, item.description, unit, item.unit), item)
            for item in items
        ]
        scored = [(score, item) for score, item in scored if score >= min_score]
        scored.sort(key=lambda x: (-x[0], x[1].price))
        return [item for score, item in scored[:limit]]
