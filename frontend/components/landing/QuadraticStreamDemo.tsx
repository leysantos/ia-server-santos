"use client";

import { useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/utils";

type StreamPhase = "idle" | "stream" | "hold";

function tokenize(text: string): string[] {
  const parts = text.match(/\S+|\s+/g);
  return parts ?? [];
}

function useTokenStream(fullText: string, opts?: { holdMs?: number; idleMs?: number }) {
  const tokens = useMemo(() => tokenize(fullText), [fullText]);
  const [count, setCount] = useState(0);
  const [phase, setPhase] = useState<StreamPhase>("idle");
  const holdMs = opts?.holdMs ?? 4200;
  const idleMs = opts?.idleMs ?? 700;

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let cancelled = false;

    const schedule = (fn: () => void, ms: number) => {
      timer = setTimeout(() => {
        if (!cancelled) fn();
      }, ms);
    };

    if (phase === "idle") {
      schedule(() => {
        setCount(0);
        setPhase("stream");
      }, idleMs);
    } else if (phase === "stream") {
      if (count >= tokens.length) {
        schedule(() => setPhase("hold"), 400);
      } else {
        const next = tokens[count] ?? "";
        const delay =
          next.includes("\n") ? 90 : /[Δ√∈Σ∑{=}]/.test(next) ? 55 : 22 + (next.length > 4 ? 8 : 0);
        schedule(() => setCount((c) => c + 1), delay);
      }
    } else if (phase === "hold") {
      schedule(() => {
        setCount(0);
        setPhase("idle");
      }, holdMs);
    }

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [phase, count, tokens, holdMs, idleMs]);

  return {
    visible: tokens.slice(0, count).join(""),
    streaming: phase === "stream",
  };
}

function DemoShell({
  badge,
  userPrompt,
  visible,
  streaming,
  className,
}: {
  badge: string;
  userPrompt: string;
  visible: string;
  streaming: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex h-[500px] flex-col overflow-hidden rounded-2xl border border-white/10 bg-slate-950/80 shadow-glow backdrop-blur-sm",
        className
      )}
      aria-hidden
    >
      <div className="flex shrink-0 items-center gap-2 border-b border-white/5 px-3 py-2">
        <span className="h-2 w-2 rounded-full bg-brand-400 animate-pulse" />
        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Chat IA · simulação
        </span>
        <span className="ml-auto rounded-full bg-brand-500/15 px-2 py-0.5 text-[10px] font-medium text-brand-300 ring-1 ring-brand-500/25">
          {badge}
        </span>
      </div>

      <div className="flex min-h-0 flex-1 flex-col space-y-3 overflow-y-auto p-3 sm:p-4">
        <div className="ml-4 shrink-0 rounded-xl rounded-tr-sm bg-brand-600/25 px-3 py-2 text-[12px] leading-relaxed text-brand-100 sm:ml-6 sm:text-[13px]">
          {userPrompt}
        </div>

        <div className="rounded-xl rounded-tl-sm border border-white/5 bg-surface-card/90 px-3 py-2.5">
          <div className="mb-1.5 flex items-center gap-2">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-gradient-to-br from-sky-400 to-brand-600 text-[9px] font-bold text-white">
              IA
            </span>
            <span className="text-[10px] text-slate-500">Assistente · streaming</span>
          </div>
          <pre className="whitespace-pre-wrap font-sans text-[12px] leading-relaxed text-slate-200 sm:text-[13px]">
            {visible}
            {streaming ? (
              <span className="landing-stream-cursor ml-0.5 inline-block h-[1em] w-[0.45em] translate-y-[0.1em] bg-brand-400 align-baseline" />
            ) : null}
          </pre>
        </div>
      </div>
    </div>
  );
}

const QUAD_PROMPT = "Resolva a equação do 2º grau: x² − 5x + 6 = 0";

const QUAD_FULL = `Solução recomendada

Equação: x² − 5x + 6 = 0
(a = 1, b = −5, c = 6)

Discriminante:
Δ = b² − 4ac = (−5)² − 4·1·6 = 25 − 24 = 1

Raízes (Bhaskara):
x = (−b ± √Δ) / (2a)
x₁ = (5 + 1) / 2 = 3
x₂ = (5 − 1) / 2 = 2

Conferência: (x − 2)(x − 3) = x² − 5x + 6 ✓

Resposta: x ∈ {2, 3}`;

const BEAM_PROMPT =
  "Viga biapoiada L = 6 m com carga distribuída q = 10 kN/m. Calcule as reações.";

const BEAM_FULL = `Solução recomendada

Modelo: viga isostática biapoiada
Apoios A (esquerdo) e B (direito)
Carga uniforme q = 10 kN/m · L = 6 m

Equilíbrio (ΣF = 0, ΣM = 0):

Carga total:
W = q · L = 10 · 6 = 60 kN

ΣFy = 0:
RA + RB − W = 0
RA + RB = 60 kN

ΣMA = 0:
RB · L − W · (L/2) = 0
RB · 6 = 60 · 3
RB = 30 kN

Logo RA = 30 kN

Conferência: simetria → RA = RB = W/2 ✓

Resposta: RA = RB = 30 kN`;

export function QuadraticStreamDemo({ className }: { className?: string }) {
  const { visible, streaming } = useTokenStream(QUAD_FULL, { idleMs: 600 });
  return (
    <DemoShell
      className={className}
      badge="ÁLGEBRA"
      userPrompt={QUAD_PROMPT}
      visible={visible}
      streaming={streaming}
    />
  );
}

export function BeamReactionsStreamDemo({ className }: { className?: string }) {
  const { visible, streaming } = useTokenStream(BEAM_FULL, { idleMs: 1400 });
  return (
    <DemoShell
      className={className}
      badge="ESTRUTURAL"
      userPrompt={BEAM_PROMPT}
      visible={visible}
      streaming={streaming}
    />
  );
}

const CONCRETE_PROMPT =
  "Dosagem de concreto fck = 25 MPa, slump 8 ± 2 cm. Trace o traço 1 : a : b e o consumo de cimento.";

const CONCRETE_FULL = `Solução recomendada

Método: dosagem racional (ABCP / IPT — simplificado)
fck = 25 MPa · slump = 8 ± 2 cm · brita 1

Resistência de dosagem:
fcm = fck + 1,65 · Sd
Sd ≈ 4 MPa → fcm = 25 + 6,6 ≈ 31,6 MPa

Água/cimento (curva típica CP II):
a/c ≈ 0,55

Consumo de água (slump 8 cm, brita 1):
Aa ≈ 190 L/m³

Cimento:
C = Aa / (a/c) = 190 / 0,55 ≈ 345 kg/m³

Agregados (massa):
areia ≈ 710 kg/m³ · brita ≈ 1080 kg/m³

Traço em massa (1 : a : b):
1 : 2,06 : 3,13
com a/c = 0,55

Conferência: C · (1+a+b) ≈ volume unitário ✓

Resposta: 1 : 2,06 : 3,13 · C ≈ 345 kg/m³`;

const TRUSS_PROMPT =
  "Treliça triangular isostática: vão 8 m, altura 3 m, carga P = 40 kN no nó do topo. Calcule o esforço axial nas barras.";

const TRUSS_FULL = `Solução recomendada

Modelo: treliça plana isostática ABC
A e B apoios · C nó do topo
L = 8 m · h = 3 m · P = 40 kN ↓ em C

Geometria (AC = BC):
ℓ = √((L/2)² + h²) = √(16 + 9) = 5 m
cos θ = (L/2)/ℓ = 4/5 = 0,80
sen θ = h/ℓ = 3/5 = 0,60

Equilíbrio no nó C (ΣFx = ΣFy = 0):
2 · N_AC · sen θ = P
N_AC = N_BC = P / (2 · 0,60) = 40 / 1,20 ≈ 33,3 kN (tração)

Tirante AB (método dos nós em A):
N_AB · 1 + N_AC · cos θ = 0
N_AB = −33,3 · 0,80 ≈ −26,7 kN (compressão)

Conferência: ΣFy apoios = P ✓

Resposta: AC=BC ≈ 33,3 kN (T) · AB ≈ 26,7 kN (C)`;

export function ConcreteMixStreamDemo({ className }: { className?: string }) {
  const { visible, streaming } = useTokenStream(CONCRETE_FULL, { idleMs: 2200 });
  return (
    <DemoShell
      className={className}
      badge="MATERIAIS"
      userPrompt={CONCRETE_PROMPT}
      visible={visible}
      streaming={streaming}
    />
  );
}

export function TrussAxialStreamDemo({ className }: { className?: string }) {
  const { visible, streaming } = useTokenStream(TRUSS_FULL, { idleMs: 3000 });
  return (
    <DemoShell
      className={className}
      badge="TRELIÇA"
      userPrompt={TRUSS_PROMPT}
      visible={visible}
      streaming={streaming}
    />
  );
}

/** @deprecated use named export QuadraticStreamDemo */
export default QuadraticStreamDemo;
