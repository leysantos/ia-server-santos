"""Croqui estrutural determinístico (viga CA) — detalhamento tipo prancha."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class BeamSpec:
    label: str = "V1"
    span_m: float = 7.0
    support_m: float = 0.15
    width_cm: float = 15.0
    height_cm: float = 60.0
    load_kgf_m: float | None = 800.0
    fck_mpa: float | None = 30.0
    cover_mm: float = 30.0
    bottom_n: int = 2
    bottom_phi: float = 16.0
    top_n: int = 2
    top_phi: float = 8.0
    stirrup_phi: float = 6.3
    stirrup_spacing_cm: float = 15.0
    steel_long: str = "CA-50"
    steel_stirrup: str = "CA-60"


def _num(s: str) -> float | None:
    try:
        return float(s.replace(",", "."))
    except Exception:
        return None


def parse_beam_spec(text: str, source_question: str | None = None) -> BeamSpec | None:
    """Extrai parâmetros de viga biapoiada do texto técnico / pergunta."""
    blob = f"{source_question or ''}\n{text or ''}"
    low = blob.lower()
    if not re.search(r"\bviga\b", low):
        return None
    if not re.search(r"bi[-\s]?apoi|simplesmente apoi|vão|vao", low):
        # ainda tenta se houver seção tipica bxh + vão
        if not re.search(r"\d+\s*[x×]\s*\d+", low):
            return None

    spec = BeamSpec()

    m = re.search(
        r"(?:dim(?:ens[aã]o)?|se[cç][aã]o|secao)?\s*(\d{1,3})\s*[x×]\s*(\d{1,3})\s*cm",
        low,
    )
    if m:
        spec.width_cm = float(m.group(1))
        spec.height_cm = float(m.group(2))

    m = re.search(r"v[aã]o(?:\s+livre)?(?:\s+de)?\s*(\d+[.,]?\d*)\s*m\b", low)
    if m:
        v = _num(m.group(1))
        if v:
            spec.span_m = v

    m = re.search(r"(\d+[.,]?\d*)\s*kgf\s*/\s*m", low)
    if m:
        spec.load_kgf_m = _num(m.group(1))
    else:
        m = re.search(r"(\d+[.,]?\d*)\s*kN\s*/\s*m", low)
        if m:
            kn = _num(m.group(1))
            if kn is not None:
                spec.load_kgf_m = kn * 100.0  # 1 kN ≈ 100 kgf

    m = re.search(r"fck\s*=?\s*(\d+[.,]?\d*)\s*mpa", low)
    if m:
        spec.fck_mpa = _num(m.group(1))

    m = re.search(r"c(?:obrimento|_?nom)?\s*[:=]?\s*(\d+[.,]?\d*)\s*mm", low)
    if m:
        v = _num(m.group(1))
        if v:
            spec.cover_mm = v

    # Inferior / tração
    m = re.search(
        r"(?:inferior|tra[cç][aã]o|longitudinal inferior)[^\n]{0,40}?"
        r"(\d+)\s*(?:[x×]|φ|fi|ø|\\phi)\s*(\d+[.,]?\d*)",
        low,
    )
    if not m:
        m = re.search(r"(\d+)\s*[φø]\s*(\d+[.,]?\d*)\s*mm[^\n]{0,30}(?:inferior|tra[cç])", low)
    if m:
        spec.bottom_n = int(m.group(1))
        spec.bottom_phi = _num(m.group(2)) or spec.bottom_phi

    # Superior / porta-estribo
    m = re.search(
        r"(?:superior|porta[-\s]?estrib)[^\n]{0,40}?"
        r"(\d+)\s*(?:[x×]|φ|fi|ø|\\phi)\s*(\d+[.,]?\d*)",
        low,
    )
    if m:
        spec.top_n = int(m.group(1))
        spec.top_phi = _num(m.group(2)) or spec.top_phi

    # Estribos
    m = re.search(
        r"estrib[^\n]{0,50}?(?:φ|fi|ø|\\phi)\s*(\d+[.,]?\d*)\s*(?:mm)?[^\n]{0,20}?"
        r"(?:c/?|a cada|espa[cç]amento)\s*(\d+[.,]?\d*)\s*cm",
        low,
    )
    if not m:
        m = re.search(
            r"(?:φ|fi|ø)\s*(\d+[.,]?\d*)\s*mm\s*c/?\s*(\d+[.,]?\d*)\s*cm",
            low,
        )
    if m:
        spec.stirrup_phi = _num(m.group(1)) or spec.stirrup_phi
        spec.stirrup_spacing_cm = _num(m.group(2)) or spec.stirrup_spacing_cm

    m = re.search(r"\bviga\s*(v?\d+)\b", low)
    if m:
        spec.label = m.group(1).upper()
        if not spec.label.startswith("V"):
            spec.label = f"V{spec.label}"

    return spec


def _steel_mass_kg_per_m(phi_mm: float) -> float:
    # π/4 * d² * 7850 kg/m³ → kg/m
    d = phi_mm / 1000.0
    return 3.1415926535 / 4.0 * d * d * 7850.0


def _steel_table(spec: BeamSpec) -> list[dict[str, Any]]:
    total_len_m = spec.span_m + 2 * spec.support_m
    # gancho ≈ 10φ + margem
    bottom_unit_cm = total_len_m * 100 + 2 * max(20.0, 10 * (spec.bottom_phi / 10))
    top_unit_cm = total_len_m * 100 + 10
    # estribo: 2*(b'+h') + ganchos — b'≈b-2c, h'≈h-2c
    b_inner = max(4.0, spec.width_cm - 2 * (spec.cover_mm / 10))
    h_inner = max(8.0, spec.height_cm - 2 * (spec.cover_mm / 10))
    stirrup_unit_cm = 2 * (b_inner + h_inner) + 2 * 8.0  # ganchos
    n_stirrups = max(3, int(round((spec.span_m * 100) / spec.stirrup_spacing_cm)) + 1)

    rows = [
        {
            "pos": "N1",
            "funcao": "Longitudinal inferior (tração)",
            "phi": f"{spec.bottom_phi:.1f} mm",
            "qtd": spec.bottom_n,
            "comp_unit_cm": round(bottom_unit_cm, 0),
            "comp_total_m": round(spec.bottom_n * bottom_unit_cm / 100, 2),
            "aco": spec.steel_long,
            "peso_kg": round(
                spec.bottom_n * (bottom_unit_cm / 100) * _steel_mass_kg_per_m(spec.bottom_phi),
                2,
            ),
        },
        {
            "pos": "N2",
            "funcao": "Porta-estribo (superior)",
            "phi": f"{spec.top_phi:.1f} mm",
            "qtd": spec.top_n,
            "comp_unit_cm": round(top_unit_cm, 0),
            "comp_total_m": round(spec.top_n * top_unit_cm / 100, 2),
            "aco": spec.steel_long,
            "peso_kg": round(
                spec.top_n * (top_unit_cm / 100) * _steel_mass_kg_per_m(spec.top_phi),
                2,
            ),
        },
        {
            "pos": "N3",
            "funcao": f"Estribos φ{spec.stirrup_phi:.1f} c/{spec.stirrup_spacing_cm:.0f} cm",
            "phi": f"{spec.stirrup_phi:.1f} mm",
            "qtd": n_stirrups,
            "comp_unit_cm": round(stirrup_unit_cm, 0),
            "comp_total_m": round(n_stirrups * stirrup_unit_cm / 100, 2),
            "aco": spec.steel_stirrup,
            "peso_kg": round(
                n_stirrups * (stirrup_unit_cm / 100) * _steel_mass_kg_per_m(spec.stirrup_phi),
                2,
            ),
        },
    ]
    # Pele se h > 60 cm
    if spec.height_cm > 60:
        rows.insert(
            2,
            {
                "pos": "N3",
                "funcao": "Armadura de pele (faces)",
                "phi": "6.3 mm",
                "qtd": 4,
                "comp_unit_cm": round(total_len_m * 100, 0),
                "comp_total_m": round(4 * total_len_m, 2),
                "aco": spec.steel_long,
                "peso_kg": round(4 * total_len_m * _steel_mass_kg_per_m(6.3), 2),
            },
        )
        rows[-1]["pos"] = "N4"
    return rows


def build_beam_detail_png(spec: BeamSpec) -> bytes:
    """Desenha elevação + seção + tabela de aço no estilo prancha estrutural."""
    from PIL import Image, ImageDraw, ImageFont

    W, H = 1600, 1100
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        font_b = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        font_s = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        font_xs = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except Exception:
        font = font_b = font_s = font_xs = ImageFont.load_default()

    ink = (15, 23, 42)
    blue = (29, 78, 216)
    gray = (100, 116, 139)

    # Cabeçalho
    title = f"VIGA {spec.label} — DETALHAMENTO ESTRUTURAL (NBR 6118)"
    draw.text((40, 24), title, fill=blue, font=font_b)
    subtitle = (
        f"Seção {spec.width_cm:.0f}×{spec.height_cm:.0f} cm · Vão {spec.span_m:.2f} m · "
        f"c = {spec.cover_mm:.0f} mm"
        + (f" · fck {spec.fck_mpa:.0f} MPa" if spec.fck_mpa else "")
        + (f" · q = {spec.load_kgf_m:.0f} kgf/m" if spec.load_kgf_m else "")
    )
    draw.text((40, 56), subtitle, fill=gray, font=font_s)
    draw.line((40, 84, W - 40, 84), fill=blue, width=2)
    draw.line((40, 90, W - 40, 90), fill=gray, width=1)

    # --- Elevação ---
    draw.text((40, 110), "1) Elevação longitudinal", fill=ink, font=font)

    # Escala horizontal
    left = 80
    right = 980
    beam_top = 220
    # altura visual proporcional (cap)
    beam_h_px = max(36, min(90, int(spec.height_cm * 1.1)))
    beam_bot = beam_top + beam_h_px
    support_w = max(18, int((spec.support_m / max(spec.span_m, 0.1)) * (right - left) * 0.35))
    support_w = min(support_w, 40)

    # Apoios
    for x0 in (left, right - support_w):
        draw.rectangle((x0, beam_bot, x0 + support_w, beam_bot + 55), outline=ink, width=2)
        # hachura apoio
        for i in range(0, 55, 6):
            draw.line((x0 + 2, beam_bot + i, x0 + support_w - 2, beam_bot + i + 8), fill=gray, width=1)

    # Viga
    draw.rectangle((left, beam_top, right, beam_bot), outline=ink, width=3)

    # Armadura inferior (linha contínua com ganchos nos apoios)
    y_bot = beam_bot - 10
    draw.line((left + 8, y_bot, right - 8, y_bot), fill=ink, width=3)
    # ganchos 90°
    draw.line((left + 8, y_bot, left + 8, beam_top + 12), fill=ink, width=3)
    draw.line((right - 8, y_bot, right - 8, beam_top + 12), fill=ink, width=3)

    # Porta-estribo superior
    y_top = beam_top + 10
    draw.line((left + 14, y_top, right - 14, y_top), fill=ink, width=2)

    # Estribos esquemáticos
    spacing_px = max(18, int((right - left - 40) / max(8, int(spec.span_m * 100 / spec.stirrup_spacing_cm))))
    x = left + 28
    while x < right - 28:
        draw.rectangle((x - 4, beam_top + 6, x + 4, beam_bot - 6), outline=ink, width=1)
        x += spacing_px

    # Carga distribuída
    if spec.load_kgf_m:
        y_load = beam_top - 55
        draw.line((left + support_w, y_load, right - support_w, y_load), fill=ink, width=2)
        n_arr = 9
        for i in range(n_arr):
            xa = left + support_w + int(i * (right - left - 2 * support_w) / (n_arr - 1))
            draw.line((xa, y_load, xa, beam_top - 6), fill=ink, width=2)
            draw.polygon([(xa, beam_top - 6), (xa - 5, beam_top - 16), (xa + 5, beam_top - 16)], fill=ink)
        draw.text(
            (left + (right - left) // 2 - 70, y_load - 28),
            f"q = {spec.load_kgf_m:.0f} kgf/m",
            fill=ink,
            font=font_s,
        )

    # Cota vão
    y_dim = beam_bot + 70
    draw.line((left + support_w, y_dim, right - support_w, y_dim), fill=ink, width=1)
    draw.line((left + support_w, y_dim - 6, left + support_w, y_dim + 6), fill=ink, width=1)
    draw.line((right - support_w, y_dim - 6, right - support_w, y_dim + 6), fill=ink, width=1)
    draw.text(
        ((left + right) // 2 - 40, y_dim + 8),
        f"L = {spec.span_m:.2f} m",
        fill=ink,
        font=font_s,
    )
    # cotas apoios
    draw.text((left - 5, beam_bot + 58), f"{spec.support_m*100:.0f}", fill=gray, font=font_xs)
    draw.text((right - support_w - 5, beam_bot + 58), f"{spec.support_m*100:.0f}", fill=gray, font=font_xs)
    draw.text((left - 5, beam_bot + 72), "cm", fill=gray, font=font_xs)

    # Cota altura viga (à esquerda)
    x_h = left - 35
    draw.line((x_h, beam_top, x_h, beam_bot), fill=ink, width=1)
    draw.line((x_h - 5, beam_top, x_h + 5, beam_top), fill=ink, width=1)
    draw.line((x_h - 5, beam_bot, x_h + 5, beam_bot), fill=ink, width=1)
    draw.text((x_h - 48, (beam_top + beam_bot) // 2 - 8), f"h={spec.height_cm:.0f}cm", fill=ink, font=font_xs)

    draw.text(
        (40, y_dim + 40),
        f"N1: {spec.bottom_n}φ{spec.bottom_phi:.0f} inf. · N2: {spec.top_n}φ{spec.top_phi:.0f} sup. · "
        f"Estribos φ{spec.stirrup_phi:.1f} c/{spec.stirrup_spacing_cm:.0f} cm (2 ramos)",
        fill=ink,
        font=font_s,
    )

    # --- Seção transversal ---
    draw.text((1080, 110), "2) Seção transversal", fill=ink, font=font)
    sx0, sy0 = 1180, 160
    # escala ~ 3.5 px/cm
    sc = 3.5
    sw = int(spec.width_cm * sc)
    sh = int(spec.height_cm * sc)
    sx1, sy1 = sx0 + sw, sy0 + sh
    draw.rectangle((sx0, sy0, sx1, sy1), outline=ink, width=3)

    # cobrimento / estribo interno
    c_px = max(6, int((spec.cover_mm / 10) * sc))
    draw.rectangle((sx0 + c_px, sy0 + c_px, sx1 - c_px, sy1 - c_px), outline=ink, width=1)

    # barras
    r_bot = max(4, int(spec.bottom_phi * sc / 8))
    r_top = max(3, int(spec.top_phi * sc / 8))
    # inferiores
    for i in range(spec.bottom_n):
        t = (i + 1) / (spec.bottom_n + 1)
        cx = int(sx0 + c_px + 6 + t * (sw - 2 * c_px - 12))
        cy = sy1 - c_px - 8
        draw.ellipse((cx - r_bot, cy - r_bot, cx + r_bot, cy + r_bot), fill=ink)
    # superiores
    for i in range(spec.top_n):
        t = (i + 1) / (spec.top_n + 1)
        cx = int(sx0 + c_px + 6 + t * (sw - 2 * c_px - 12))
        cy = sy0 + c_px + 8
        draw.ellipse((cx - r_top, cy - r_top, cx + r_top, cy + r_top), fill=ink)

    # cotas seção
    draw.line((sx0, sy1 + 18, sx1, sy1 + 18), fill=ink, width=1)
    draw.text(((sx0 + sx1) // 2 - 30, sy1 + 22), f"b = {spec.width_cm:.0f} cm", fill=ink, font=font_xs)
    draw.line((sx1 + 18, sy0, sx1 + 18, sy1), fill=ink, width=1)
    draw.text((sx1 + 24, (sy0 + sy1) // 2 - 8), f"h = {spec.height_cm:.0f} cm", fill=ink, font=font_xs)
    d_cm = spec.height_cm - spec.cover_mm / 10 - spec.stirrup_phi / 10 - spec.bottom_phi / 20
    draw.text((sx0 - 10, sy1 + 48), f"c = {spec.cover_mm:.0f} mm", fill=gray, font=font_xs)
    draw.text((sx0 - 10, sy1 + 66), f"d ≈ {d_cm:.1f} cm", fill=gray, font=font_xs)
    draw.text(
        (sx0 - 10, sy1 + 84),
        f"{spec.bottom_n}φ{spec.bottom_phi:.0f} / {spec.top_n}φ{spec.top_phi:.0f}",
        fill=ink,
        font=font_xs,
    )

    # --- Tabela de aço ---
    table_top = 520
    draw.text((40, table_top), "3) Tabela de aço — detalhamento", fill=ink, font=font)
    headers = ["Pos.", "Função", "φ", "Qtd.", "Comp. unit. (cm)", "Comp. total (m)", "Aço", "Peso (kg)"]
    col_w = [70, 320, 100, 70, 160, 150, 90, 100]
    x0, y0 = 40, table_top + 36
    row_h = 32
    # header bg
    draw.rectangle((x0, y0, x0 + sum(col_w), y0 + row_h), fill=(232, 238, 249), outline=ink, width=1)
    x = x0
    for htxt, w in zip(headers, col_w):
        draw.text((x + 6, y0 + 8), htxt, fill=ink, font=font_xs)
        x += w
    rows = _steel_table(spec)
    y = y0 + row_h
    for row in rows:
        vals = [
            row["pos"],
            row["funcao"],
            row["phi"],
            str(row["qtd"]),
            f"{row['comp_unit_cm']:.0f}",
            f"{row['comp_total_m']:.2f}".replace(".", ","),
            row["aco"],
            f"{row['peso_kg']:.2f}".replace(".", ","),
        ]
        draw.rectangle((x0, y, x0 + sum(col_w), y + row_h), outline=ink, width=1)
        x = x0
        for val, w in zip(vals, col_w):
            draw.text((x + 6, y + 8), val[:42], fill=ink, font=font_xs)
            draw.line((x, y, x, y + row_h), fill=ink, width=1)
            x += w
        y += row_h

    total = sum(r["peso_kg"] for r in rows)
    ca50 = sum(r["peso_kg"] for r in rows if r["aco"] == "CA-50")
    ca60 = sum(r["peso_kg"] for r in rows if r["aco"] == "CA-60")
    draw.text(
        (40, y + 16),
        f"Consumo: CA-50 = {ca50:.2f} kg · CA-60 = {ca60:.2f} kg · Total = {total:.2f} kg "
        f"(1 elemento · comprimento total ≈ {spec.span_m + 2*spec.support_m:.2f} m)",
        fill=ink,
        font=font_s,
    )
    draw.text(
        (40, y + 44),
        "Croqui gerado deterministicamente pelo IA Server Santos (layout de prancha). "
        "Validar cotas, ancoragens e bitolas com o projetista responsável.",
        fill=gray,
        font=font_xs,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def try_build_structural_croqui(
    text: str,
    source_question: str | None = None,
) -> tuple[bytes, str] | None:
    """Tenta croqui determinístico; None se não reconhecer o elemento."""
    spec = parse_beam_spec(text, source_question)
    if not spec:
        return None
    return build_beam_detail_png(spec), "image/png"
