"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/services/api";
import type {
  InspectionVisualMemoryItem,
  InspectionVisualOverlay,
  InspectionVisualOverlayType,
} from "@/types/api";

type Tool = "select" | InspectionVisualOverlayType;

type DragMode =
  | { kind: "none" }
  | { kind: "create"; startX: number; startY: number }
  | { kind: "move"; id: string; startX: number; startY: number; orig: number[] }
  | { kind: "handle"; id: string; handle: number; startX: number; startY: number; orig: number[] };

const HANDLE_R = 7;
const HIT_PAD = 0.025;
const DEFAULT_COLOR = "#dc2626";
const DEFAULT_STROKE = 3;
const DEFAULT_FONT = 16;

const COLOR_PRESETS = [
  "#dc2626",
  "#ea580c",
  "#ca8a04",
  "#16a34a",
  "#2563eb",
  "#7c3aed",
  "#ffffff",
  "#0f172a",
] as const;

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `vm_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v));
}

function dist(ax: number, ay: number, bx: number, by: number): number {
  return Math.hypot(ax - bx, ay - by);
}

function withStyle(
  base: Omit<InspectionVisualOverlay, "color" | "stroke" | "font_size" | "filled"> &
    Partial<InspectionVisualOverlay>,
  style: { color: string; stroke: number; fontSize: number; filled: boolean }
): InspectionVisualOverlay {
  return {
    ...base,
    color: style.color,
    stroke: style.stroke,
    font_size: style.fontSize,
    filled: style.filled,
  };
}

function overlayHandles(o: InspectionVisualOverlay): Array<{ i: number; x: number; y: number }> {
  const p = o.points;
  if ((o.type === "line" || o.type === "arrow") && p.length >= 4) {
    return [
      { i: 0, x: p[0], y: p[1] },
      { i: 1, x: p[2], y: p[3] },
    ];
  }
  if ((o.type === "rect" || o.type === "circle") && p.length >= 4) {
    const x0 = Math.min(p[0], p[2]);
    const y0 = Math.min(p[1], p[3]);
    const x1 = Math.max(p[0], p[2]);
    const y1 = Math.max(p[1], p[3]);
    return [
      { i: 0, x: x0, y: y0 },
      { i: 1, x: x1, y: y0 },
      { i: 2, x: x1, y: y1 },
      { i: 3, x: x0, y: y1 },
    ];
  }
  if (o.type === "label" && p.length >= 2) {
    return [{ i: 0, x: p[0], y: p[1] }];
  }
  return [];
}

function hitHandle(
  o: InspectionVisualOverlay,
  x: number,
  y: number,
  tol: number
): number | null {
  for (const h of overlayHandles(o)) {
    if (dist(x, y, h.x, h.y) <= tol) return h.i;
  }
  return null;
}

function hitOverlay(o: InspectionVisualOverlay, x: number, y: number): boolean {
  const p = o.points;
  if ((o.type === "line" || o.type === "arrow") && p.length >= 4) {
    const x0 = p[0];
    const y0 = p[1];
    const x1 = p[2];
    const y1 = p[3];
    const dx = x1 - x0;
    const dy = y1 - y0;
    const len2 = dx * dx + dy * dy || 1e-9;
    let t = ((x - x0) * dx + (y - y0) * dy) / len2;
    t = Math.max(0, Math.min(1, t));
    return dist(x, y, x0 + t * dx, y0 + t * dy) < HIT_PAD;
  }
  if ((o.type === "rect" || o.type === "circle") && p.length >= 4) {
    const x0 = Math.min(p[0], p[2]) - HIT_PAD;
    const y0 = Math.min(p[1], p[3]) - HIT_PAD;
    const x1 = Math.max(p[0], p[2]) + HIT_PAD;
    const y1 = Math.max(p[1], p[3]) + HIT_PAD;
    return x >= x0 && x <= x1 && y >= y0 && y <= y1;
  }
  if (o.type === "label" && p.length >= 2) {
    return dist(x, y, p[0], p[1]) < HIT_PAD * 1.5;
  }
  return false;
}

function applyHandleMove(
  o: InspectionVisualOverlay,
  handle: number,
  x: number,
  y: number
): number[] {
  const nx = clamp01(x);
  const ny = clamp01(y);
  if (o.type === "line" || o.type === "arrow") {
    const pts = [...o.points];
    if (handle === 0) {
      pts[0] = nx;
      pts[1] = ny;
    } else {
      pts[2] = nx;
      pts[3] = ny;
    }
    return pts;
  }
  if (o.type === "rect" || o.type === "circle") {
    let x0 = Math.min(o.points[0], o.points[2]);
    let y0 = Math.min(o.points[1], o.points[3]);
    let x1 = Math.max(o.points[0], o.points[2]);
    let y1 = Math.max(o.points[1], o.points[3]);
    if (handle === 0) {
      x0 = nx;
      y0 = ny;
    } else if (handle === 1) {
      x1 = nx;
      y0 = ny;
    } else if (handle === 2) {
      x1 = nx;
      y1 = ny;
    } else {
      x0 = nx;
      y1 = ny;
    }
    return [x0, y0, x1, y1];
  }
  if (o.type === "label") {
    return [nx, ny];
  }
  return o.points;
}

function translateOverlay(points: number[], dx: number, dy: number): number[] {
  return points.map((v, i) => clamp01(v + (i % 2 === 0 ? dx : dy)));
}

function hexToRgba(hex: string, alpha: number): string {
  const h = (hex || DEFAULT_COLOR).replace("#", "");
  const full =
    h.length === 3 ? `${h[0]}${h[0]}${h[1]}${h[1]}${h[2]}${h[2]}` : h.padEnd(6, "0");
  const r = parseInt(full.slice(0, 2), 16) || 220;
  const g = parseInt(full.slice(2, 4), 16) || 38;
  const b = parseInt(full.slice(4, 6), 16) || 38;
  return `rgba(${r},${g},${b},${alpha})`;
}

export default function InspectionVisualMemoryEditor({
  reportId,
  disabled,
  onSaved,
}: {
  reportId: string;
  disabled?: boolean;
  onSaved?: () => void;
}) {
  const [items, setItems] = useState<InspectionVisualMemoryItem[]>([]);
  const [photos, setPhotos] = useState<
    Array<{ asset_id: string; filename: string; photo_number?: number | null; caption?: string | null }>
  >([]);
  const [assetId, setAssetId] = useState("");
  const [tool, setTool] = useState<Tool>("select");
  const [overlays, setOverlays] = useState<InspectionVisualOverlay[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<InspectionVisualOverlay | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);

  // Estilo da caneta (novos elementos) / espelhado no selecionado
  const [penColor, setPenColor] = useState(DEFAULT_COLOR);
  const [penStroke, setPenStroke] = useState(DEFAULT_STROKE);
  const [penFont, setPenFont] = useState(DEFAULT_FONT);
  const [penFilled, setPenFilled] = useState(true);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const dragRef = useRef<DragMode>({ kind: "none" });
  const overlaysRef = useRef(overlays);
  overlaysRef.current = overlays;

  const selected = overlays.find((o) => o.id === selectedId) || null;
  const styleNow = {
    color: penColor,
    stroke: penStroke,
    fontSize: penFont,
    filled: penFilled,
  };

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getInspectionVisualMemory(reportId);
      setItems(data.items || []);
      setPhotos(data.photos || []);
      if (!assetId && data.photos?.[0]) {
        setAssetId(data.photos[0].asset_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [reportId, assetId]);

  useEffect(() => {
    load().catch(() => undefined);
  }, [load]);

  useEffect(() => {
    const existing = items.find((i) => i.asset_id === assetId);
    setOverlays(existing?.overlays || []);
    setSelectedId(null);
    setDraft(null);
    setDirty(false);
    dragRef.current = { kind: "none" };
  }, [assetId, items]);

  useEffect(() => {
    if (!selected) return;
    setPenColor(selected.color || DEFAULT_COLOR);
    setPenStroke(selected.stroke ?? DEFAULT_STROKE);
    setPenFont(selected.font_size ?? DEFAULT_FONT);
    setPenFilled(selected.filled ?? true);
  }, [selectedId]); // eslint-disable-line react-hooks/exhaustive-deps -- sync only on selection change

  useEffect(() => {
    if (!assetId) {
      setPreviewUrl(null);
      return;
    }
    let revoked: string | null = null;
    let cancelled = false;
    (async () => {
      try {
        const blob = await api.fetchInspectionReportAssetFile(reportId, assetId);
        if (cancelled) return;
        const url = URL.createObjectURL(blob);
        revoked = url;
        setPreviewUrl(url);
      } catch {
        if (!cancelled) setPreviewUrl(null);
      }
    })();
    return () => {
      cancelled = true;
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [reportId, assetId]);

  const normFromEvent = (e: React.PointerEvent | PointerEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    return {
      x: clamp01((e.clientX - rect.left) / rect.width),
      y: clamp01((e.clientY - rect.top) / rect.height),
    };
  };

  const redraw = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img || !img.complete || !img.naturalWidth) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const maxW = canvas.parentElement?.clientWidth || 640;
    const scale = Math.min(1, maxW / img.naturalWidth);
    const w = Math.round(img.naturalWidth * scale);
    const h = Math.round(img.naturalHeight * scale);
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    ctx.clearRect(0, 0, w, h);
    ctx.drawImage(img, 0, 0, w, h);

    const drawOne = (o: InspectionVisualOverlay, isSelected: boolean) => {
      const pts = o.points;
      const text = [o.label, o.unit].filter(Boolean).join(" ");
      const color = o.color || DEFAULT_COLOR;
      const stroke = o.stroke ?? DEFAULT_STROKE;
      const fontSize = o.font_size ?? DEFAULT_FONT;
      const filled = o.filled ?? true;
      const lw = Math.max(1, Math.round((Math.min(w, h) / 220) * (stroke / 2)));
      const fs = Math.max(10, Math.round(fontSize * (Math.min(w, h) / 900)));

      ctx.lineWidth = lw;
      ctx.font = `600 ${fs}px sans-serif`;
      ctx.strokeStyle = isSelected ? "#38bdf8" : color;
      ctx.fillStyle = isSelected ? "#38bdf8" : color;

      if ((o.type === "line" || o.type === "arrow") && pts.length >= 4) {
        const [x0, y0, x1, y1] = [pts[0] * w, pts[1] * h, pts[2] * w, pts[3] * h];
        ctx.beginPath();
        ctx.moveTo(x0, y0);
        ctx.lineTo(x1, y1);
        ctx.stroke();
        if (o.type === "arrow") {
          const ang = Math.atan2(y1 - y0, x1 - x0);
          const size = Math.max(10, lw * 4);
          ctx.beginPath();
          ctx.moveTo(x1, y1);
          ctx.lineTo(x1 - size * Math.cos(ang - 0.4), y1 - size * Math.sin(ang - 0.4));
          ctx.lineTo(x1 - size * Math.cos(ang + 0.4), y1 - size * Math.sin(ang + 0.4));
          ctx.closePath();
          ctx.fill();
        }
        if (text) {
          const mx = (x0 + x1) / 2;
          const my = (y0 + y1) / 2 - fs * 0.7;
          const tw = ctx.measureText(text).width;
          ctx.fillStyle = "rgba(15,23,42,0.8)";
          ctx.fillRect(mx - 4, my - fs, tw + 8, fs + 6);
          ctx.fillStyle = isSelected ? "#7dd3fc" : color;
          ctx.fillText(text, mx, my);
        }
      } else if (o.type === "rect" && pts.length >= 4) {
        const x = Math.min(pts[0], pts[2]) * w;
        const y = Math.min(pts[1], pts[3]) * h;
        const rw = Math.abs(pts[2] - pts[0]) * w;
        const rh = Math.abs(pts[3] - pts[1]) * h;
        if (filled) {
          ctx.fillStyle = hexToRgba(color, 0.12);
          ctx.fillRect(x, y, rw, rh);
        }
        ctx.strokeRect(x, y, rw, rh);
        if (text) {
          ctx.fillStyle = "rgba(15,23,42,0.85)";
          const tw = ctx.measureText(text).width;
          ctx.fillRect(x + 4, y + 4, tw + 8, fs + 6);
          ctx.fillStyle = isSelected ? "#7dd3fc" : color;
          ctx.fillText(text, x + 8, y + fs + 2);
        }
      } else if (o.type === "circle" && pts.length >= 4) {
        const x0 = Math.min(pts[0], pts[2]) * w;
        const y0 = Math.min(pts[1], pts[3]) * h;
        const x1 = Math.max(pts[0], pts[2]) * w;
        const y1 = Math.max(pts[1], pts[3]) * h;
        const cx = (x0 + x1) / 2;
        const cy = (y0 + y1) / 2;
        const rx = Math.abs(x1 - x0) / 2;
        const ry = Math.abs(y1 - y0) / 2;
        ctx.beginPath();
        ctx.ellipse(cx, cy, Math.max(1, rx), Math.max(1, ry), 0, 0, Math.PI * 2);
        if (filled) {
          ctx.fillStyle = hexToRgba(color, 0.12);
          ctx.fill();
        }
        ctx.stroke();
        if (text) {
          const tw = ctx.measureText(text).width;
          ctx.fillStyle = "rgba(15,23,42,0.85)";
          ctx.fillRect(cx - tw / 2 - 4, cy - fs / 2 - 2, tw + 8, fs + 6);
          ctx.fillStyle = isSelected ? "#7dd3fc" : color;
          ctx.fillText(text, cx - tw / 2, cy + fs / 3);
        }
      } else if (o.type === "label" && pts.length >= 2) {
        const x = pts[0] * w;
        const y = pts[1] * h;
        ctx.beginPath();
        ctx.arc(x, y, Math.max(5, lw + 2), 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 1.5;
        ctx.stroke();
        ctx.lineWidth = lw;
        const labelText = text || "•";
        const tw = ctx.measureText(labelText).width;
        ctx.fillStyle = "rgba(15,23,42,0.88)";
        ctx.fillRect(x + 10, y - fs - 8, tw + 10, fs + 8);
        ctx.strokeStyle = isSelected ? "#38bdf8" : color;
        ctx.strokeRect(x + 10, y - fs - 8, tw + 10, fs + 8);
        ctx.fillStyle = isSelected ? "#7dd3fc" : color;
        ctx.fillText(labelText, x + 15, y - 6);
        ctx.beginPath();
        ctx.moveTo(x + 5, y - 4);
        ctx.lineTo(x + 10, y - 12);
        ctx.stroke();
      }

      if (isSelected) {
        for (const handle of overlayHandles(o)) {
          ctx.fillStyle = "#fff";
          ctx.strokeStyle = "#0284c7";
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(handle.x * w, handle.y * h, HANDLE_R, 0, Math.PI * 2);
          ctx.fill();
          ctx.stroke();
        }
      }
    };

    for (const o of overlays) {
      drawOne(o, o.id === selectedId);
    }
    if (draft) drawOne(draft, true);
  }, [overlays, selectedId, draft]);

  useEffect(() => {
    redraw();
  }, [redraw, previewUrl]);

  useEffect(() => {
    const onResize = () => redraw();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [redraw]);

  const updateOverlay = (id: string, patch: Partial<InspectionVisualOverlay>) => {
    setOverlays((prev) => prev.map((o) => (o.id === id ? { ...o, ...patch } : o)));
    setDirty(true);
  };

  const applyStyleToSelectedOrPen = (patch: {
    color?: string;
    stroke?: number;
    fontSize?: number;
    filled?: boolean;
  }) => {
    if (patch.color != null) setPenColor(patch.color);
    if (patch.stroke != null) setPenStroke(patch.stroke);
    if (patch.fontSize != null) setPenFont(patch.fontSize);
    if (patch.filled != null) setPenFilled(patch.filled);
    if (selectedId) {
      updateOverlay(selectedId, {
        ...(patch.color != null ? { color: patch.color } : {}),
        ...(patch.stroke != null ? { stroke: patch.stroke } : {}),
        ...(patch.fontSize != null ? { font_size: patch.fontSize } : {}),
        ...(patch.filled != null ? { filled: patch.filled } : {}),
      });
    }
  };

  const onPointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (disabled) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    const { x, y } = normFromEvent(e);

    if (tool === "select") {
      if (selectedId) {
        const sel = overlaysRef.current.find((o) => o.id === selectedId);
        if (sel) {
          const hi = hitHandle(sel, x, y, HIT_PAD);
          if (hi != null) {
            dragRef.current = {
              kind: "handle",
              id: sel.id,
              handle: hi,
              startX: x,
              startY: y,
              orig: [...sel.points],
            };
            return;
          }
        }
      }
      const list = [...overlaysRef.current].reverse();
      const hit = list.find((o) => hitOverlay(o, x, y) || hitHandle(o, x, y, HIT_PAD) != null);
      if (hit) {
        setSelectedId(hit.id);
        setTool("select");
        dragRef.current = {
          kind: "move",
          id: hit.id,
          startX: x,
          startY: y,
          orig: [...hit.points],
        };
        return;
      }
      setSelectedId(null);
      dragRef.current = { kind: "none" };
      return;
    }

    setSelectedId(null);
    if (tool === "label") {
      const id = newId();
      const created = withStyle(
        { id, type: "label", points: [x, y], label: "", unit: "" },
        styleNow
      );
      setOverlays((prev) => [...prev, created]);
      setSelectedId(id);
      setTool("select");
      setDirty(true);
      dragRef.current = { kind: "none" };
      return;
    }

    dragRef.current = { kind: "create", startX: x, startY: y };
    setDraft(
      withStyle(
        {
          id: "draft",
          type: tool,
          points: [x, y, x, y],
          label: "",
          unit: tool === "line" || tool === "arrow" ? "mm" : "",
        },
        styleNow
      )
    );
  };

  const onPointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (disabled) return;
    const { x, y } = normFromEvent(e);
    const drag = dragRef.current;

    if (drag.kind === "create") {
      const t: InspectionVisualOverlayType = tool === "select" ? "line" : tool;
      setDraft(
        withStyle(
          {
            id: "draft",
            type: t,
            points: [drag.startX, drag.startY, x, y],
            label: "",
            unit: t === "line" || t === "arrow" ? "mm" : "",
          },
          styleNow
        )
      );
      return;
    }

    if (drag.kind === "move") {
      const dx = x - drag.startX;
      const dy = y - drag.startY;
      setOverlays((prev) =>
        prev.map((o) =>
          o.id === drag.id ? { ...o, points: translateOverlay(drag.orig, dx, dy) } : o
        )
      );
      setDirty(true);
      return;
    }

    if (drag.kind === "handle") {
      setOverlays((prev) =>
        prev.map((o) => {
          if (o.id !== drag.id) return o;
          const base = { ...o, points: drag.orig };
          return { ...o, points: applyHandleMove(base, drag.handle, x, y) };
        })
      );
      setDirty(true);
    }
  };

  const onPointerUp = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const drag = dragRef.current;
    dragRef.current = { kind: "none" };
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      /* ignore */
    }

    if (drag.kind === "create" && draft) {
      const pts = draft.points;
      const tooSmall =
        (draft.type === "line" ||
          draft.type === "arrow" ||
          draft.type === "rect" ||
          draft.type === "circle") &&
        dist(pts[0], pts[1], pts[2], pts[3]) < 0.02;
      if (!tooSmall) {
        const id = newId();
        const created: InspectionVisualOverlay = { ...draft, id };
        setOverlays((prev) => [...prev, created]);
        setSelectedId(id);
        setTool("select");
        setDirty(true);
      }
      setDraft(null);
    }
  };

  const save = async () => {
    if (!assetId) return;
    setSaving(true);
    setError(null);
    try {
      const photo = photos.find((p) => p.asset_id === assetId);
      const others = items.filter((i) => i.asset_id !== assetId);
      const nextItem: InspectionVisualMemoryItem = {
        id: items.find((i) => i.asset_id === assetId)?.id || newId(),
        asset_id: assetId,
        photo_number: photo?.photo_number ?? null,
        overlays,
      };
      const data = await api.saveInspectionVisualMemory(reportId, [...others, nextItem]);
      setItems(data.items || []);
      setDirty(false);
      onSaved?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const deleteSelected = () => {
    if (!selectedId) return;
    setOverlays((prev) => prev.filter((o) => o.id !== selectedId));
    setSelectedId(null);
    setDirty(true);
  };

  const duplicateSelected = () => {
    if (!selected) return;
    const id = newId();
    const pts = translateOverlay(selected.points, 0.03, 0.03);
    setOverlays((prev) => [...prev, { ...selected, id, points: pts }]);
    setSelectedId(id);
    setDirty(true);
  };

  if (!photos.length && !loading) {
    return (
      <p className="text-xs text-slate-500">
        Adicione fotos ao laudo para criar croquis cotados (L17).
      </p>
    );
  }

  const cursorClass =
    tool === "select" ? "cursor-default" : tool === "label" ? "cursor-cell" : "cursor-crosshair";

  const tools: Array<[Tool, string]> = [
    ["select", "Selecionar"],
    ["label", "Texto / marcador"],
    ["line", "Linha cotada"],
    ["arrow", "Seta"],
    ["rect", "Retângulo"],
    ["circle", "Círculo"],
  ];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-white">Croqui cotado (L17)</h3>
          <p className="mt-0.5 text-xs text-slate-500">
            Ferramentas + cor, espessura e texto · arraste e ajuste pelos pontos azuis.
          </p>
        </div>
        <button
          type="button"
          disabled={disabled || saving || !assetId || !dirty}
          onClick={save}
          className="rounded-lg bg-cyan-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-cyan-600 disabled:opacity-50"
        >
          {saving ? "Salvando…" : dirty ? "Salvar croqui" : "Salvo"}
        </button>
      </div>

      {error ? (
        <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-200">{error}</p>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <label className="text-xs text-slate-400">
          Foto
          <select
            className="ml-2 rounded-lg border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
            value={assetId}
            disabled={disabled}
            onChange={(e) => setAssetId(e.target.value)}
          >
            {photos.map((p) => (
              <option key={p.asset_id} value={p.asset_id}>
                Foto {String(p.photo_number || "").padStart(2, "0")} — {p.filename}
              </option>
            ))}
          </select>
        </label>

        {tools.map(([id, name]) => (
          <button
            key={id}
            type="button"
            disabled={disabled}
            onClick={() => {
              setTool(id);
              setDraft(null);
              if (id !== "select") setSelectedId(null);
            }}
            className={`rounded-md px-2.5 py-1 text-[11px] font-medium ${
              tool === id
                ? "bg-brand-600 text-white"
                : "bg-slate-800 text-slate-300 hover:bg-slate-700"
            }`}
          >
            {name}
          </button>
        ))}

        <button
          type="button"
          disabled={disabled || !selectedId}
          onClick={duplicateSelected}
          className="rounded-md bg-slate-800 px-2 py-1 text-[11px] text-slate-300 hover:bg-slate-700 disabled:opacity-40"
        >
          Duplicar
        </button>
        <button
          type="button"
          disabled={disabled || !selectedId}
          onClick={deleteSelected}
          className="rounded-md bg-rose-900/60 px-2 py-1 text-[11px] text-rose-100 hover:bg-rose-800 disabled:opacity-40"
        >
          Excluir
        </button>
        <button
          type="button"
          disabled={disabled || overlays.length === 0}
          onClick={() => {
            setOverlays([]);
            setSelectedId(null);
            setDirty(true);
          }}
          className="rounded-md bg-slate-800 px-2 py-1 text-[11px] text-slate-300 hover:bg-slate-700 disabled:opacity-40"
        >
          Limpar tudo
        </button>
      </div>

      {/* Painel de estilo — caneta ou elemento selecionado */}
      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-700/80 bg-slate-950/70 px-3 py-2.5">
        <p className="w-full text-[11px] font-medium uppercase tracking-wide text-slate-400">
          {selected ? `Estilo — ${selected.type}` : "Estilo da caneta (próximo desenho)"}
        </p>

        <div className="space-y-1">
          <span className="text-[11px] text-slate-400">Cor</span>
          <div className="flex flex-wrap items-center gap-1.5">
            {COLOR_PRESETS.map((c) => (
              <button
                key={c}
                type="button"
                title={c}
                disabled={disabled}
                onClick={() => applyStyleToSelectedOrPen({ color: c })}
                className={`h-6 w-6 rounded-md border-2 ${
                  penColor.toLowerCase() === c ? "border-cyan-400 ring-1 ring-cyan-400/50" : "border-slate-600"
                }`}
                style={{ backgroundColor: c }}
              />
            ))}
            <label className="ml-1 flex items-center gap-1 text-[11px] text-slate-400">
              <input
                type="color"
                value={penColor.startsWith("#") && penColor.length === 7 ? penColor : DEFAULT_COLOR}
                disabled={disabled}
                onChange={(e) => applyStyleToSelectedOrPen({ color: e.target.value })}
                className="h-6 w-8 cursor-pointer rounded border border-slate-600 bg-transparent"
              />
            </label>
          </div>
        </div>

        <label className="text-xs text-slate-400">
          Espessura
          <div className="mt-1 flex items-center gap-2">
            <input
              type="range"
              min={1}
              max={12}
              value={penStroke}
              disabled={disabled}
              onChange={(e) => applyStyleToSelectedOrPen({ stroke: Number(e.target.value) })}
              className="w-28"
            />
            <span className="w-5 tabular-nums text-[11px] text-slate-300">{penStroke}</span>
          </div>
        </label>

        <label className="text-xs text-slate-400">
          Texto (tamanho)
          <div className="mt-1 flex items-center gap-2">
            <input
              type="range"
              min={10}
              max={48}
              value={penFont}
              disabled={disabled}
              onChange={(e) => applyStyleToSelectedOrPen({ fontSize: Number(e.target.value) })}
              className="w-28"
            />
            <span className="w-6 tabular-nums text-[11px] text-slate-300">{penFont}</span>
          </div>
        </label>

        {(tool === "rect" ||
          tool === "circle" ||
          selected?.type === "rect" ||
          selected?.type === "circle") && (
          <label className="flex items-center gap-2 pb-1 text-xs text-slate-400">
            <input
              type="checkbox"
              checked={penFilled}
              disabled={disabled}
              onChange={(e) => applyStyleToSelectedOrPen({ filled: e.target.checked })}
              className="rounded border-slate-600"
            />
            Preenchimento
          </label>
        )}

        {selected ? (
          <>
            <label className="text-xs text-slate-400">
              Cota / rótulo
              <input
                className="mt-1 block w-40 rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-white"
                value={selected.label || ""}
                disabled={disabled}
                placeholder="ex.: Fundação exposta"
                onChange={(e) => updateOverlay(selected.id, { label: e.target.value })}
              />
            </label>
            <label className="text-xs text-slate-400">
              Unidade
              <input
                className="mt-1 block w-20 rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-white"
                value={selected.unit || ""}
                disabled={disabled}
                placeholder="mm"
                onChange={(e) => updateOverlay(selected.id, { unit: e.target.value })}
              />
            </label>
          </>
        ) : (
          <p className="pb-1.5 text-[11px] text-slate-500">
            {tool === "select"
              ? "Selecione um elemento para editar texto e estilo."
              : tool === "label"
                ? "Clique na foto para colocar o marcador."
                : "Clique e arraste para desenhar com o estilo atual."}
          </p>
        )}
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-700 bg-slate-950 touch-none">
        {previewUrl ? (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              ref={imgRef}
              src={previewUrl}
              alt="Foto para croqui"
              className="hidden"
              onLoad={redraw}
            />
            <canvas
              ref={canvasRef}
              className={`max-w-full ${cursorClass}`}
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
              onPointerCancel={onPointerUp}
            />
          </>
        ) : (
          <p className="px-3 py-8 text-center text-xs text-slate-500">
            {loading ? "Carregando…" : "Selecione uma foto"}
          </p>
        )}
      </div>
      <p className="text-[11px] text-slate-500">
        {overlays.length} anotação(ões)
        {dirty ? " · alterações não salvas" : ""}
      </p>
    </div>
  );
}
