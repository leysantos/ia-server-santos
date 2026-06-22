"""Erros de sincronização SINAPI com mensagens acionáveis."""

from __future__ import annotations

from pricing.sync.sinapi_links import sinapi_national_zip_url


class SinapiDownloadError(Exception):
    code: str = "SINAPI_DOWNLOAD_FAILED"

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": str(self),
            "action": getattr(self, "action", "retry_or_upload"),
            "help_url": getattr(self, "help_url", None),
        }


class SinapiDownloadBlockedError(SinapiDownloadError):
    """Caixa bloqueia download automatizado (WAF / resposta HTML em vez do ZIP)."""

    code = "CAIXA_BLOCKED"
    action = "upload_manual"

    def __init__(
        self,
        uf: str = "SP",
        period: str = "",
        *,
        status_code: int | None = None,
        tried: list[str] | None = None,
    ) -> None:
        from pricing.sync.sinapi_links import sinapi_national_downloads_url

        self.help_url = sinapi_national_downloads_url()
        self.status_code = status_code
        if period and "-" in period:
            try:
                y, m = period.split("-", 1)
                self.help_url = sinapi_national_zip_url(int(y), int(m))
            except ValueError:
                pass
        period_hint = f" ({period})" if period else ""
        tried_hint = ""
        if tried:
            tried_hint = f" Meses testados: {', '.join(tried)}."
        http_hint = f" HTTP {status_code}" if status_code else ""
        super().__init__(
            "A Caixa devolveu página HTML em vez do ZIP SINAPI"
            f"{http_hint}{period_hint} — bloqueio anti-bot ou mês sem publicação no servidor.{tried_hint} "
            "O download automático consulta o portal configurado (categoria do link) e baixa o ZIP XLSX do período, incluindo retificações. "
            f"Se falhar, baixe manualmente em {sinapi_national_downloads_url()} ou use Importar arquivo local "
            f"(UF de referência: {uf})."
        )


class SinapiPeriodNotFoundError(SinapiDownloadError):
    code = "SINAPI_NOT_FOUND"
    action = "upload_manual"

    def __init__(self, uf: str, tried: list[str]) -> None:
        from pricing.sync.sinapi_links import sinapi_national_downloads_url

        self.help_url = sinapi_national_downloads_url()
        if len(tried) == 1:
            msg = (
                f"O ZIP SINAPI de {tried[0]} não está publicado na Caixa "
                "(a URL devolve página HTML em vez do arquivo). "
                "Escolha um mês já disponível (ex.: 03/2026–05/2026) "
                f"ou baixe em {sinapi_national_downloads_url()} e use Importar arquivo local."
            )
        else:
            msg = (
                f"Nenhum ZIP SINAPI nacional nos meses tentados: {', '.join(tried)}. "
                f"Baixe em {sinapi_national_downloads_url()} ou use Importar arquivo local."
            )
        super().__init__(msg)
