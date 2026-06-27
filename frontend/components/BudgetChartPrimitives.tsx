"use client";

import { useCallback, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface ChartMargins {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

const DEFAULT_MARGINS: ChartMargins = { top: 16, right: 16, bottom: 36, left: 52 };

interface HoverState {
  index: number;
  x: number;
  y: number;
}

function scaleLinear(value: number, domainMax: number, rangeMax: number): number {
  if (domainMax <= 0) return 0;
  return (value / domainMax) * rangeMax;
}

export function ChartTooltipCard({
  visible,
  x,
  y,
  containerWidth,
  children,
  className,
}: {
  visible: boolean;
  x: number;
  y: number;
  containerWidth?: number;
  children: ReactNode;
  className?: string;
}) {
  if (!visible) return null;

  const flipBelow = y < 80;
  const clampedX =
    containerWidth != null
      ? Math.min(Math.max(x, 120), containerWidth - 120)
      : x;

  return (
    <div
      className={cn(
        "pointer-events-none absolute z-20 min-w-[10rem] max-w-[16rem] rounded-lg bg-slate-950/95 px-3 py-2.5 text-xs shadow-xl ring-1 ring-slate-600/80 backdrop-blur-sm",
        className
      )}
      style={{
        left: clampedX,
        top: y,
        transform: flipBelow
          ? "translate(-50%, 12px)"
          : "translate(-50%, calc(-100% - 12px))",
      }}
    >
      {children}
      <span
        className={cn(
          "absolute left-1/2 -translate-x-1/2 border-4 border-transparent",
          flipBelow ? "bottom-full border-b-slate-600/80" : "top-full border-t-slate-600/80"
        )}
        aria-hidden
      />
    </div>
  );
}

function useChartHover() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<HoverState | null>(null);

  const setHoverFromEvent = useCallback((index: number, clientX: number, clientY: number) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    setHover({
      index,
      x: clientX - rect.left,
      y: clientY - rect.top,
    });
  }, []);

  const clearHover = useCallback(() => setHover(null), []);

  return { containerRef, hover, setHoverFromEvent, clearHover };
}

export function BudgetLineChart({
  width = 720,
  height = 280,
  labels,
  series,
  yMax = 100,
  ySuffix = "%",
  className,
  renderTooltip,
}: {
  width?: number;
  height?: number;
  labels: string[];
  series: { name: string; color: string; values: number[] }[];
  yMax?: number;
  ySuffix?: string;
  className?: string;
  renderTooltip?: (index: number) => ReactNode;
}) {
  const m = DEFAULT_MARGINS;
  const innerW = width - m.left - m.right;
  const innerH = height - m.top - m.bottom;
  const n = Math.max(1, labels.length);
  const stepX = innerW / Math.max(1, n - 1);
  const interactive = Boolean(renderTooltip);
  const { containerRef, hover, setHoverFromEvent, clearHover } = useChartHover();

  const yTicks = [0, 25, 50, 75, 100].filter((t) => t <= yMax);
  const activeIndex = hover?.index ?? null;

  return (
    <div
      ref={containerRef}
      className={cn("relative", interactive && "cursor-crosshair")}
      onMouseLeave={interactive ? clearHover : undefined}
    >
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className={cn("w-full max-w-full text-slate-400", className)}
        role="img"
        aria-label="Gráfico de linhas"
      >
        {yTicks.map((tick) => {
          const y = m.top + innerH - scaleLinear(tick, yMax, innerH);
          return (
            <g key={tick}>
              <line
                x1={m.left}
                y1={y}
                x2={width - m.right}
                y2={y}
                stroke="currentColor"
                strokeOpacity={0.12}
              />
              <text x={m.left - 8} y={y + 4} textAnchor="end" fontSize={10} fill="currentColor">
                {tick}
                {ySuffix}
              </text>
            </g>
          );
        })}

        {activeIndex !== null && (
          <line
            x1={m.left + activeIndex * stepX}
            y1={m.top}
            x2={m.left + activeIndex * stepX}
            y2={m.top + innerH}
            stroke="#94a3b8"
            strokeOpacity={0.35}
            strokeDasharray="4 3"
          />
        )}

        {labels.map((label, i) => {
          const x = m.left + i * stepX;
          const dimmed = activeIndex !== null && activeIndex !== i;
          return (
            <text
              key={`${label}-${i}`}
              x={x}
              y={height - 8}
              textAnchor="middle"
              fontSize={9}
              fill="currentColor"
              opacity={dimmed ? 0.35 : 0.85}
            >
              {label}
            </text>
          );
        })}

        {series.map((s) => {
          const points = s.values
            .map((v, i) => {
              const x = m.left + i * stepX;
              const y = m.top + innerH - scaleLinear(v, yMax, innerH);
              return `${x},${y}`;
            })
            .join(" ");

          return (
            <polyline
              key={s.name}
              fill="none"
              stroke={s.color}
              strokeWidth={activeIndex !== null ? 2.5 : 2}
              strokeLinejoin="round"
              strokeLinecap="round"
              points={points}
              opacity={activeIndex !== null ? 0.95 : 1}
            />
          );
        })}

        {series.map((s) =>
          s.values.map((v, i) => {
            const x = m.left + i * stepX;
            const y = m.top + innerH - scaleLinear(v, yMax, innerH);
            const isActive = activeIndex === i;
            const dimmed = activeIndex !== null && !isActive;
            return (
              <circle
                key={`${s.name}-${i}`}
                cx={x}
                cy={y}
                r={isActive ? 5 : 3}
                fill={s.color}
                opacity={dimmed ? 0.35 : 1}
                stroke={isActive ? "#f8fafc" : "none"}
                strokeWidth={isActive ? 1.5 : 0}
              />
            );
          })
        )}

        {interactive &&
          labels.map((label, i) => {
            const slotX = m.left + i * stepX;
            const hitW = i === 0 || i === labels.length - 1 ? stepX / 2 : stepX;
            const hitX = i === 0 ? slotX : i === labels.length - 1 ? slotX - hitW : slotX - hitW / 2;
            return (
              <rect
                key={`hit-${label}-${i}`}
                x={hitX}
                y={m.top}
                width={hitW}
                height={innerH}
                fill="transparent"
                onMouseEnter={(e) => setHoverFromEvent(i, e.clientX, e.clientY)}
                onMouseMove={(e) => setHoverFromEvent(i, e.clientX, e.clientY)}
              />
            );
          })}
      </svg>

      {interactive && hover !== null && renderTooltip && (
        <ChartTooltipCard
          visible
          x={hover.x}
          y={hover.y}
          containerWidth={containerRef.current?.clientWidth}
        >
          {renderTooltip(hover.index)}
        </ChartTooltipCard>
      )}
    </div>
  );
}

export function BudgetGroupedBarChart({
  width = 720,
  height = 300,
  labels,
  groups,
  className,
}: {
  width?: number;
  height?: number;
  labels: string[];
  groups: { key: string; label: string; color: string; values: number[] }[];
  className?: string;
}) {
  const m = DEFAULT_MARGINS;
  const innerW = width - m.left - m.right;
  const innerH = height - m.top - m.bottom;
  const n = Math.max(1, labels.length);
  const groupCount = Math.max(1, groups.length);

  const stackedMax = labels.map((_, i) =>
    groups.reduce((sum, g) => sum + (g.values[i] ?? 0), 0)
  );
  const yMax = Math.max(1, ...stackedMax);

  const slotW = innerW / n;
  const barW = Math.min(18, (slotW - 8) / groupCount);

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * yMax);

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className={cn("w-full max-w-full text-slate-400", className)}
      role="img"
      aria-label="Gráfico de barras agrupadas"
    >
      {yTicks.map((tick, idx) => {
        const y = m.top + innerH - scaleLinear(tick, yMax, innerH);
        return (
          <g key={idx}>
            <line
              x1={m.left}
              y1={y}
              x2={width - m.right}
              y2={y}
              stroke="currentColor"
              strokeOpacity={0.12}
            />
            <text x={m.left - 8} y={y + 4} textAnchor="end" fontSize={10} fill="currentColor">
              {tick >= 1_000_000
                ? `${(tick / 1_000_000).toFixed(1)}M`
                : tick >= 1_000
                  ? `${(tick / 1_000).toFixed(0)}k`
                  : Math.round(tick).toLocaleString("pt-BR")}
            </text>
          </g>
        );
      })}

      {labels.map((label, i) => {
        const slotX = m.left + i * slotW + slotW / 2;
        const groupOffset = ((groupCount - 1) * barW) / 2;

        return (
          <g key={`${label}-${i}`}>
            {groups.map((g, gi) => {
              const value = g.values[i] ?? 0;
              const barH = scaleLinear(value, yMax, innerH);
              const x = slotX - groupOffset + gi * barW;
              const y = m.top + innerH - barH;
              return (
                <rect
                  key={g.key}
                  x={x}
                  y={y}
                  width={barW - 2}
                  height={Math.max(0, barH)}
                  fill={g.color}
                  rx={2}
                  opacity={0.9}
                >
                  <title>{`${g.label} · ${label}: ${value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}`}</title>
                </rect>
              );
            })}
            <text
              x={slotX}
              y={height - 8}
              textAnchor="middle"
              fontSize={9}
              fill="currentColor"
              opacity={0.85}
            >
              {label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function BudgetParetoChart({
  width = 720,
  height = 300,
  labels,
  barValues,
  cumulativePct,
  barColors,
  className,
  renderTooltip,
}: {
  width?: number;
  height?: number;
  labels: string[];
  barValues: number[];
  cumulativePct: number[];
  barColors?: string[];
  className?: string;
  renderTooltip?: (index: number) => ReactNode;
}) {
  const m = { ...DEFAULT_MARGINS, right: 48 };
  const innerW = width - m.left - m.right;
  const innerH = height - m.top - m.bottom;
  const n = Math.max(1, labels.length);
  const barMax = Math.max(1, ...barValues);
  const slotW = innerW / n;
  const barW = Math.min(28, slotW * 0.7);
  const interactive = Boolean(renderTooltip);
  const { containerRef, hover, setHoverFromEvent, clearHover } = useChartHover();
  const activeIndex = hover?.index ?? null;

  return (
    <div
      ref={containerRef}
      className={cn("relative", interactive && "cursor-crosshair")}
      onMouseLeave={interactive ? clearHover : undefined}
    >
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className={cn("w-full max-w-full text-slate-400", className)}
        role="img"
        aria-label="Curva ABC"
      >
        {[0, 0.25, 0.5, 0.75, 1].map((f) => {
          const tick = f * barMax;
          const y = m.top + innerH - scaleLinear(tick, barMax, innerH);
          return (
            <g key={f}>
              <line
                x1={m.left}
                y1={y}
                x2={width - m.right}
                y2={y}
                stroke="currentColor"
                strokeOpacity={0.12}
              />
              <text x={m.left - 8} y={y + 4} textAnchor="end" fontSize={10} fill="currentColor">
                {tick >= 1_000 ? `${(tick / 1_000).toFixed(0)}k` : Math.round(tick)}
              </text>
            </g>
          );
        })}

        {[0, 25, 50, 75, 100].map((pct) => {
          const y = m.top + innerH - scaleLinear(pct, 100, innerH);
          return (
            <text
              key={pct}
              x={width - m.right + 8}
              y={y + 4}
              textAnchor="start"
              fontSize={10}
              fill="#38bdf8"
            >
              {pct}%
            </text>
          );
        })}

        {activeIndex !== null && (
          <line
            x1={m.left + activeIndex * slotW + slotW / 2}
            y1={m.top}
            x2={m.left + activeIndex * slotW + slotW / 2}
            y2={m.top + innerH}
            stroke="#94a3b8"
            strokeOpacity={0.35}
            strokeDasharray="4 3"
          />
        )}

        {labels.map((label, i) => {
          const slotX = m.left + i * slotW + slotW / 2;
          const value = barValues[i] ?? 0;
          const barH = scaleLinear(value, barMax, innerH);
          const color = barColors?.[i] ?? "#64748b";
          const isActive = activeIndex === i;
          const dimmed = activeIndex !== null && !isActive;
          return (
            <g key={`${label}-${i}`}>
              <rect
                x={slotX - barW / 2}
                y={m.top + innerH - barH}
                width={barW}
                height={barH}
                fill={color}
                rx={2}
                opacity={dimmed ? 0.35 : isActive ? 1 : 0.85}
                stroke={isActive ? "#f8fafc" : "none"}
                strokeWidth={isActive ? 1 : 0}
              />
              <text
                x={slotX}
                y={height - 8}
                textAnchor="middle"
                fontSize={8}
                fill="currentColor"
                opacity={dimmed ? 0.35 : 0.75}
              >
                {label.length > 10 ? `${label.slice(0, 9)}…` : label}
              </text>
            </g>
          );
        })}

        <polyline
          fill="none"
          stroke="#38bdf8"
          strokeWidth={activeIndex !== null ? 2.5 : 2}
          points={cumulativePct
            .map((pct, i) => {
              const x = m.left + i * slotW + slotW / 2;
              const y = m.top + innerH - scaleLinear(pct, 100, innerH);
              return `${x},${y}`;
            })
            .join(" ")}
        />

        {cumulativePct.map((pct, i) => {
          const x = m.left + i * slotW + slotW / 2;
          const y = m.top + innerH - scaleLinear(pct, 100, innerH);
          const isActive = activeIndex === i;
          const dimmed = activeIndex !== null && !isActive;
          return (
            <circle
              key={`cum-${i}`}
              cx={x}
              cy={y}
              r={isActive ? 5 : 3}
              fill="#38bdf8"
              opacity={dimmed ? 0.35 : 1}
              stroke={isActive ? "#f8fafc" : "none"}
              strokeWidth={isActive ? 1.5 : 0}
            />
          );
        })}

        {interactive &&
          labels.map((label, i) => (
            <rect
              key={`hit-${label}-${i}`}
              x={m.left + i * slotW}
              y={m.top}
              width={slotW}
              height={innerH}
              fill="transparent"
              onMouseEnter={(e) => setHoverFromEvent(i, e.clientX, e.clientY)}
              onMouseMove={(e) => setHoverFromEvent(i, e.clientX, e.clientY)}
            />
          ))}
      </svg>

      {interactive && hover !== null && renderTooltip && (
        <ChartTooltipCard
          visible
          x={hover.x}
          y={hover.y}
          containerWidth={containerRef.current?.clientWidth}
        >
          {renderTooltip(hover.index)}
        </ChartTooltipCard>
      )}
    </div>
  );
}

/** Barras verticais totais por período — modelo planilha Caixa (histograma.pdf) */
export function BudgetHistogramBarChart({
  width = 720,
  height = 320,
  periodLabels,
  values,
  barColor = "#38bdf8",
  yMax: yMaxProp,
  className,
  renderTooltip,
}: {
  width?: number;
  height?: number;
  periodLabels: string[];
  values: number[];
  barColor?: string;
  yMax?: number;
  className?: string;
  renderTooltip?: (index: number) => ReactNode;
}) {
  const m = DEFAULT_MARGINS;
  const innerW = width - m.left - m.right;
  const innerH = height - m.top - m.bottom;
  const n = Math.max(1, periodLabels.length);
  const dataMax = Math.max(1, ...values, 0);
  const yMax = yMaxProp ?? niceCeil(dataMax * 1.1);
  const slotW = innerW / n;
  const barW = Math.min(36, slotW * 0.65);
  const interactive = Boolean(renderTooltip);
  const { containerRef, hover, setHoverFromEvent, clearHover } = useChartHover();
  const activeIndex = hover?.index ?? null;

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * yMax);

  return (
    <div
      ref={containerRef}
      className={cn("relative", interactive && "cursor-crosshair")}
      onMouseLeave={interactive ? clearHover : undefined}
    >
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className={cn("w-full max-w-full text-slate-400", className)}
        role="img"
        aria-label="Histograma de demanda"
      >
        {yTicks.map((tick, idx) => {
          const y = m.top + innerH - scaleLinear(tick, yMax, innerH);
          return (
            <g key={idx}>
              <line
                x1={m.left}
                y1={y}
                x2={width - m.right}
                y2={y}
                stroke="currentColor"
                strokeOpacity={0.12}
              />
              <text x={m.left - 8} y={y + 4} textAnchor="end" fontSize={10} fill="currentColor">
                {formatAxisTick(tick)}
              </text>
            </g>
          );
        })}

        {activeIndex !== null && (
          <line
            x1={m.left + activeIndex * slotW + slotW / 2}
            y1={m.top}
            x2={m.left + activeIndex * slotW + slotW / 2}
            y2={m.top + innerH}
            stroke="#94a3b8"
            strokeOpacity={0.35}
            strokeDasharray="4 3"
          />
        )}

        {periodLabels.map((label, i) => {
          const slotX = m.left + i * slotW + slotW / 2;
          const value = values[i] ?? 0;
          const barH = scaleLinear(value, yMax, innerH);
          const isActive = activeIndex === i;
          const dimmed = activeIndex !== null && !isActive;
          return (
            <g key={`${label}-${i}`}>
              <rect
                x={slotX - barW / 2}
                y={m.top + innerH - barH}
                width={barW}
                height={Math.max(0, barH)}
                fill={barColor}
                rx={3}
                opacity={dimmed ? 0.35 : isActive ? 1 : 0.88}
                stroke={isActive ? "#f8fafc" : "none"}
                strokeWidth={isActive ? 1.5 : 0}
              />
              <text
                x={slotX}
                y={height - 8}
                textAnchor="middle"
                fontSize={9}
                fill="currentColor"
                opacity={dimmed ? 0.35 : 0.9}
              >
                {label}
              </text>
            </g>
          );
        })}

        {interactive &&
          periodLabels.map((label, i) => (
            <rect
              key={`hit-${label}-${i}`}
              x={m.left + i * slotW}
              y={m.top}
              width={slotW}
              height={innerH}
              fill="transparent"
              onMouseEnter={(e) => setHoverFromEvent(i, e.clientX, e.clientY)}
              onMouseMove={(e) => setHoverFromEvent(i, e.clientX, e.clientY)}
            />
          ))}
      </svg>

      {interactive && hover !== null && renderTooltip && (
        <ChartTooltipCard
          visible
          x={hover.x}
          y={hover.y}
          containerWidth={containerRef.current?.clientWidth}
          className="max-w-[18rem]"
        >
          {renderTooltip(hover.index)}
        </ChartTooltipCard>
      )}
    </div>
  );
}

function niceCeil(value: number): number {
  if (value <= 10) return 10;
  if (value <= 50) return Math.ceil(value / 5) * 5;
  if (value <= 100) return Math.ceil(value / 10) * 10;
  return Math.ceil(value / 50) * 50;
}

function formatAxisTick(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}k`;
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

/** Barras verticais empilhadas por categoria (insumos, equipamentos, mão de obra) */
export function BudgetStackedBarChart({
  width = 720,
  height = 340,
  periodLabels,
  stacks,
  referenceSeries,
  className,
  renderTooltip,
}: {
  width?: number;
  height?: number;
  periodLabels: string[];
  stacks: { key: string; label: string; color: string; values: number[] }[];
  /** Série de referência (ex.: total com BDI) — linha tracejada com marcadores */
  referenceSeries?: { label: string; color: string; values: number[] };
  className?: string;
  renderTooltip?: (index: number) => ReactNode;
}) {
  const m = DEFAULT_MARGINS;
  const innerW = width - m.left - m.right;
  const innerH = height - m.top - m.bottom;
  const n = Math.max(1, periodLabels.length);
  const slotW = innerW / n;
  const barW = Math.min(40, slotW * 0.7);

  const stackedTotals = periodLabels.map((_, i) =>
    stacks.reduce((sum, s) => sum + (s.values[i] ?? 0), 0)
  );
  const refMax = referenceSeries
    ? Math.max(0, ...referenceSeries.values.map((v) => v ?? 0))
    : 0;
  const dataMax = Math.max(1, ...stackedTotals, refMax, 0);
  const yMax = niceCeil(dataMax * 1.1);
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * yMax);

  const refPoints =
    referenceSeries?.values.map((value, i) => {
      const slotX = m.left + i * slotW + slotW / 2;
      const y = m.top + innerH - scaleLinear(value ?? 0, yMax, innerH);
      return { x: slotX, y, value: value ?? 0 };
    }) ?? [];

  const refPolyline =
    refPoints.length > 1
      ? refPoints.map((p) => `${p.x},${p.y}`).join(" ")
      : "";

  const interactive = Boolean(renderTooltip);
  const { containerRef, hover, setHoverFromEvent, clearHover } = useChartHover();
  const activeIndex = hover?.index ?? null;

  return (
    <div
      ref={containerRef}
      className={cn("relative", interactive && "cursor-crosshair")}
      onMouseLeave={interactive ? clearHover : undefined}
    >
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className={cn("w-full max-w-full text-slate-400", className)}
        role="img"
        aria-label="Histograma empilhado"
      >
        {yTicks.map((tick, idx) => {
          const y = m.top + innerH - scaleLinear(tick, yMax, innerH);
          return (
            <g key={idx}>
              <line
                x1={m.left}
                y1={y}
                x2={width - m.right}
                y2={y}
                stroke="currentColor"
                strokeOpacity={0.12}
              />
              <text x={m.left - 8} y={y + 4} textAnchor="end" fontSize={10} fill="currentColor">
                {formatAxisTick(tick)}
              </text>
            </g>
          );
        })}

        {activeIndex !== null && (
          <line
            x1={m.left + activeIndex * slotW + slotW / 2}
            y1={m.top}
            x2={m.left + activeIndex * slotW + slotW / 2}
            y2={m.top + innerH}
            stroke="#94a3b8"
            strokeOpacity={0.35}
            strokeDasharray="4 3"
          />
        )}

        {periodLabels.map((label, i) => {
          const slotX = m.left + i * slotW + slotW / 2;
          const isActive = activeIndex === i;
          const dimmed = activeIndex !== null && !isActive;
          let yCursor = m.top + innerH;

          return (
            <g key={`${label}-${i}`}>
              {stacks.map((stack) => {
                const value = stack.values[i] ?? 0;
                if (value <= 0) return null;
                const segH = scaleLinear(value, yMax, innerH);
                yCursor -= segH;
                return (
                  <rect
                    key={stack.key}
                    x={slotX - barW / 2}
                    y={yCursor}
                    width={barW}
                    height={Math.max(0, segH)}
                    fill={stack.color}
                    opacity={dimmed ? 0.35 : isActive ? 1 : 0.9}
                    stroke={isActive ? "rgba(248,250,252,0.25)" : "none"}
                    strokeWidth={0.5}
                  />
                );
              })}
              <text
                x={slotX}
                y={height - 8}
                textAnchor="middle"
                fontSize={9}
                fill="currentColor"
                opacity={dimmed ? 0.35 : 0.9}
              >
                {label}
              </text>
            </g>
          );
        })}

        {refPolyline && referenceSeries && (
          <g aria-label={referenceSeries.label}>
            <polyline
              points={refPolyline}
              fill="none"
              stroke={referenceSeries.color}
              strokeWidth={2}
              strokeDasharray="5 4"
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity={0.95}
            />
            {refPoints.map((p, i) =>
              p.value > 0 ? (
                <circle
                  key={`ref-${i}`}
                  cx={p.x}
                  cy={p.y}
                  r={4}
                  fill={referenceSeries.color}
                  stroke="#0f172a"
                  strokeWidth={1}
                  opacity={activeIndex === null || activeIndex === i ? 1 : 0.35}
                />
              ) : null
            )}
          </g>
        )}

        {interactive &&
          periodLabels.map((label, i) => (
            <rect
              key={`hit-${label}-${i}`}
              x={m.left + i * slotW}
              y={m.top}
              width={slotW}
              height={innerH}
              fill="transparent"
              onMouseEnter={(e) => setHoverFromEvent(i, e.clientX, e.clientY)}
              onMouseMove={(e) => setHoverFromEvent(i, e.clientX, e.clientY)}
            />
          ))}
      </svg>

      {interactive && hover !== null && renderTooltip && (
        <ChartTooltipCard
          visible
          x={hover.x}
          y={hover.y}
          containerWidth={containerRef.current?.clientWidth}
          className="max-w-[18rem]"
        >
          {renderTooltip(hover.index)}
        </ChartTooltipCard>
      )}
    </div>
  );
}

export function ChartLegend({
  items,
  className,
}: {
  items: { label: string; color: string }[];
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap gap-4 text-xs text-slate-400", className)}>
      {items.map((item) => (
        <span key={item.label} className="inline-flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: item.color }} />
          {item.label}
        </span>
      ))}
    </div>
  );
}
