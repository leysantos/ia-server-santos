"""Análise quantitativa/qualitativa de patologias + gráficos (Pillow)."""

from __future__ import annotations

import io
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps


SEVERITY_ORDER = ("crítica", "alta", "média", "baixa")
SEVERITY_COLORS = {
    "crítica": (220, 38, 38),
    "alta": (234, 88, 12),
    "média": (202, 138, 4),
    "baixa": (22, 163, 74),
}


def _norm_sev(value: Any) -> str:
    s = str(value or "").strip().lower()
    s = s.replace("critica", "crítica").replace("media", "média")
    if s.startswith("crít"):
        return "crítica"
    if s.startswith("alt"):
        return "alta"
    if s.startswith("méd") or s.startswith("med"):
        return "média"
    if s.startswith("baix"):
        return "baixa"
    return s or "média"


def _score_of(p: dict[str, Any]) -> float:
    try:
        return float(p.get("score") or 0)
    except (TypeError, ValueError):
        sev = _norm_sev(p.get("severity"))
        return {"crítica": 5, "alta": 4, "média": 3, "baixa": 2}.get(sev, 3)


def prepare_watermark_png(
    image_bytes: bytes,
    *,
    size_px: int = 1600,
    opacity: float = 0.10,
    max_width_px: int | None = None,
) -> bytes | None:
    """Brasão semi-transparente para marca d'água (mantém proporção; largura alvo opcional)."""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        target_w = max_width_px or size_px
        # Redimensiona pela largura (corpo da página), preservando aspecto
        if img.width <= 0 or img.height <= 0:
            return None
        ratio = target_w / float(img.width)
        new_w = max(1, int(target_w))
        new_h = max(1, int(img.height * ratio))
        # Limita altura excessiva (~altura útil A4 ~ 2300px a 150dpi)
        max_h = int(size_px * 1.35)
        if new_h > max_h:
            scale = max_h / float(new_h)
            new_w = max(1, int(new_w * scale))
            new_h = max_h
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        alpha = img.split()[3].point(lambda p: int(p * max(0.04, min(0.35, opacity))))
        img.putalpha(alpha)
        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()
    except Exception:
        return None


def open_image_upright(source: str | Path | bytes | Image.Image) -> Image.Image:
    """
    Abre imagem aplicando EXIF Orientation (retrato/paisagem corretos).

    Celulares gravam pixels frequentemente em paisagem + tag Orientation=6/8;
    Word/PDF e ReportLab não aplicam esse tag — sem transpose a foto sai de lado.
    """
    if isinstance(source, Image.Image):
        img = source
    elif isinstance(source, (bytes, bytearray)):
        img = Image.open(io.BytesIO(source))
    else:
        img = Image.open(source)
    try:
        upright = ImageOps.exif_transpose(img)
    except Exception:
        upright = img
    if upright is None:
        upright = img
    # Cópia em memória (fecha file handle do path)
    return upright.copy()


def image_bytes_for_export(
    source: str | Path | bytes,
    *,
    max_edge_px: int = 2400,
    format: str = "JPEG",
    quality: int = 90,
) -> bytes:
    """PNG/JPEG já rotacionado conforme EXIF, sem tag Orientation residual."""
    img = open_image_upright(source)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    w, h = img.size
    edge = max(w, h)
    if edge > max_edge_px > 0:
        scale = max_edge_px / float(edge)
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    fmt = (format or "JPEG").upper()
    if fmt == "JPEG":
        img.save(buf, format="JPEG", quality=quality, optimize=True)
    else:
        img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def fit_image_display_inches(
    path: str,
    *,
    max_w: float = 5.9,
    max_h: float = 5.2,
) -> tuple[float, float]:
    """Calcula largura/altura em polegadas após corrigir EXIF (evita páginas em branco)."""
    try:
        im = open_image_upright(path)
        w, h = im.size
        if w <= 0 or h <= 0:
            return max_w, max_h * 0.7
        aspect = w / h
        if aspect >= 1:
            dw, dh = max_w, max_w / aspect
        else:
            dh, dw = max_h, max_h * aspect
        if dh > max_h:
            dh = max_h
            dw = dh * aspect
        if dw > max_w:
            dw = max_w
            dh = dw / aspect
        return max(1.5, dw), max(1.5, dh)
    except Exception:
        return 5.5, 4.0


def build_pathology_analytics(content: dict[str, Any]) -> dict[str, Any]:
    """
    Cards, tabelas e PNGs de gráficos a partir de pathologies / indicators / photos.
    """
    pathologies = list(content.get("pathologies") or [])
    photos = list(content.get("photographic_report") or [])
    indicators = content.get("indicators") or {}

    # Contagem por severidade (prioriza pathologies; complementa com fotos)
    counts: Counter[str] = Counter()
    for p in pathologies:
        counts[_norm_sev(p.get("severity"))] += 1
    if not counts and photos:
        for ph in photos:
            counts[_norm_sev(ph.get("severity"))] += 1

    total = sum(counts.values()) or len(pathologies) or len(photos) or 1
    dist_pct = {
        sev: round(100.0 * counts.get(sev, 0) / total, 1) for sev in SEVERITY_ORDER
    }

    scores = [_score_of(p) for p in pathologies] or [
        float(ph.get("score") or 3) for ph in photos if ph.get("score") is not None
    ]
    avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
    compromise = indicators.get("compromise_index_pct")
    if compromise is None:
        # peso: crítica=1, alta=0.75, média=0.45, baixa=0.2
        weights = {"crítica": 1.0, "alta": 0.75, "média": 0.45, "baixa": 0.2}
        compromise = round(
            100.0 * sum(counts.get(s, 0) * weights[s] for s in SEVERITY_ORDER) / total, 1
        )
    conservation = indicators.get("conservation_index_pct")
    if conservation is None:
        conservation = round(max(0.0, 100.0 - float(compromise)), 1)

    cards = [
        {"label": "Total de patologias", "value": str(total), "hint": "inventário técnico"},
        {
            "label": "Críticas",
            "value": f"{counts.get('crítica', 0)} ({dist_pct['crítica']}%)",
            "hint": "prioridade máxima",
        },
        {
            "label": "Altas",
            "value": f"{counts.get('alta', 0)} ({dist_pct['alta']}%)",
            "hint": "intervenção urgente",
        },
        {
            "label": "Médias / Baixas",
            "value": (
                f"{counts.get('média', 0) + counts.get('baixa', 0)} "
                f"({round(dist_pct['média'] + dist_pct['baixa'], 1)}%)"
            ),
            "hint": "monitorar / programar",
        },
        {
            "label": "Índice de comprometimento",
            "value": f"{compromise}%",
            "hint": f"conservação aparente {conservation}%",
        },
        {
            "label": "Score médio",
            "value": f"{avg_score}/5",
            "hint": f"{round(100 * avg_score / 5, 1)}% da escala",
        },
    ]

    # Ranking da mais severa para a menos severa
    ranked = sorted(
        pathologies,
        key=lambda p: (_score_of(p), {"crítica": 4, "alta": 3, "média": 2, "baixa": 1}.get(_norm_sev(p.get("severity")), 0)),
        reverse=True,
    )
    ranking_rows = []
    for i, p in enumerate(ranked, start=1):
        sev = _norm_sev(p.get("severity"))
        sc = _score_of(p)
        ranking_rows.append(
            [
                str(i),
                p.get("code") or f"P{i:02d}",
                p.get("name") or "—",
                p.get("location") or "—",
                sev.upper(),
                f"{sc:g}/5",
                f"{round(100 * sc / 5, 1)}%",
                p.get("urgency") or "—",
            ]
        )

    dist_rows = [
        [
            sev.upper(),
            str(counts.get(sev, 0)),
            f"{dist_pct[sev]}%",
            "█" * max(1, int(round(dist_pct[sev] / 5))) if counts.get(sev, 0) else "—",
        ]
        for sev in SEVERITY_ORDER
    ]

    bar_png = _render_bar_chart(
        labels=[s.upper() for s in SEVERITY_ORDER],
        values=[counts.get(s, 0) for s in SEVERITY_ORDER],
        colors=[SEVERITY_COLORS[s] for s in SEVERITY_ORDER],
        title="Quantidade de patologias por gravidade",
    )
    pie_png = _render_pie_chart(
        labels=[s.upper() for s in SEVERITY_ORDER],
        values=[counts.get(s, 0) for s in SEVERITY_ORDER],
        colors=[SEVERITY_COLORS[s] for s in SEVERITY_ORDER],
        title="Distribuição percentual por gravidade",
    )
    score_png = _render_bar_chart(
        labels=[(p.get("code") or f"P{i}")[:8] for i, p in enumerate(ranked[:12], 1)],
        values=[_score_of(p) for p in ranked[:12]],
        colors=[SEVERITY_COLORS.get(_norm_sev(p.get("severity")), (100, 116, 139)) for p in ranked[:12]],
        title="Ranking de criticidade (score 1–5)",
        y_max=5,
    )

    summary_paras = [
        (
            f"A análise quantitativa identificou {total} patologia(s) inventariada(s), "
            f"com índice de comprometimento de {compromise}% e índice de conservação aparente "
            f"de {conservation}%. O score médio de gravidade é {avg_score}/5 "
            f"({round(100 * avg_score / 5, 1)}% da escala)."
        ),
        (
            "Distribuição por gravidade: "
            + "; ".join(f"{s}: {counts.get(s, 0)} ({dist_pct[s]}%)" for s in SEVERITY_ORDER)
            + ". A ordenação a seguir apresenta as anomalias da mais severa para a menos severa, "
            "fundamentando a priorização das intervenções."
        ),
    ]

    return {
        "cards": cards,
        "summary_paragraphs": summary_paras,
        "tables": [
            {
                "caption": "Tabela A — Distribuição quantitativa por gravidade",
                "headers": ["Gravidade", "Quantidade", "Percentual", "Intensidade"],
                "rows": dist_rows,
            },
            {
                "caption": "Tabela B — Ranking de criticidade (mais severa → menos severa)",
                "headers": [
                    "Rank",
                    "Código",
                    "Patologia",
                    "Local",
                    "Severidade",
                    "Score",
                    "% Score",
                    "Urgência",
                ],
                "rows": ranking_rows,
            },
        ],
        "charts": [
            {"caption": "Gráfico 1 — Quantidade por gravidade", "png": bar_png},
            {"caption": "Gráfico 2 — Distribuição percentual", "png": pie_png},
            {"caption": "Gráfico 3 — Ranking de scores", "png": score_png},
        ],
        "metrics": {
            "total": total,
            "counts": dict(counts),
            "dist_pct": dist_pct,
            "compromise_index_pct": compromise,
            "conservation_index_pct": conservation,
            "avg_score": avg_score,
        },
    }


def _font(size: int):
    for name in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _render_bar_chart(
    *,
    labels: list[str],
    values: list[float],
    colors: list[tuple[int, int, int]],
    title: str,
    y_max: float | None = None,
) -> bytes:
    w, h = 920, 420
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    font_t = _font(18)
    font = _font(13)
    draw.text((24, 16), title, fill=(15, 23, 42), font=font_t)

    plot_l, plot_t, plot_r, plot_b = 70, 60, w - 30, h - 50
    draw.rectangle([plot_l, plot_t, plot_r, plot_b], outline=(148, 163, 184), width=1)

    n = max(1, len(labels))
    vmax = y_max if y_max is not None else max(values + [1])
    bar_w = (plot_r - plot_l) / n * 0.65
    gap = (plot_r - plot_l) / n
    for i, (lab, val, col) in enumerate(zip(labels, values, colors)):
        x0 = plot_l + i * gap + (gap - bar_w) / 2
        bh = 0 if vmax <= 0 else (val / vmax) * (plot_b - plot_t - 10)
        y0 = plot_b - bh
        draw.rectangle([x0, y0, x0 + bar_w, plot_b], fill=col)
        draw.text((x0, plot_b + 8), str(lab)[:10], fill=(71, 85, 105), font=font)
        draw.text((x0, y0 - 18), f"{val:g}", fill=(15, 23, 42), font=font)

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _render_pie_chart(
    *,
    labels: list[str],
    values: list[float],
    colors: list[tuple[int, int, int]],
    title: str,
) -> bytes:
    w, h = 920, 460
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    font_t = _font(18)
    font = _font(14)
    draw.text((24, 16), title, fill=(15, 23, 42), font=font_t)

    total = sum(values) or 1
    cx, cy, r = 280, 250, 150
    start = -90.0
    for val, col in zip(values, colors):
        if val <= 0:
            continue
        extent = 360.0 * val / total
        draw.pieslice(
            [cx - r, cy - r, cx + r, cy + r],
            start=start,
            end=start + extent,
            fill=col,
            outline=(255, 255, 255),
        )
        start += extent

    # legenda
    y = 100
    for lab, val, col in zip(labels, values, colors):
        pct = 100.0 * val / total
        draw.rectangle([560, y, 580, y + 18], fill=col)
        draw.text((595, y), f"{lab}: {val:g} ({pct:.1f}%)", fill=(15, 23, 42), font=font)
        y += 36

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()
