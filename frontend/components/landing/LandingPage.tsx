"use client";

import { FormEvent, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/services/api";
import { cn } from "@/lib/utils";
import QuadraticStreamDemo, {
  BeamReactionsStreamDemo,
} from "@/components/landing/QuadraticStreamDemo";

const NAV = [
  { href: "#recursos", label: "Recursos" },
  { href: "#modulos", label: "Módulos" },
  { href: "#casos", label: "Casos de sucesso" },
  { href: "#contato", label: "Contato" },
] as const;

const PILLARS = [
  {
    title: "Inteligência Artificial",
    desc: "Agentes especializados por disciplina com RAG normativo.",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
      />
    ),
  },
  {
    title: "Dados Integrados",
    desc: "SINAPI, SICRO, NBR e projetos no mesmo fluxo.",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"
      />
    ),
  },
  {
    title: "Soluções Completas",
    desc: "Do chat técnico ao orçamento e ao laudo assinado.",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
      />
    ),
  },
] as const;

const BENEFITS = [
  {
    title: "Performance",
    desc: "Pipeline local com Ollama, streaming SSE e cache semântico para respostas técnicas rápidas.",
    icon: "M13 10V3L4 14h7v7l9-11h-7z",
  },
  {
    title: "Segurança",
    desc: "Auth JWT, papéis e permissões por módulo. Dados sensíveis sob controle da equipe.",
    icon: "M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z",
  },
  {
    title: "Integração",
    desc: "Bases de preço, FAISS normativo, Gemini opcional e export PDF/Word institucionais.",
    icon: "M11 4a2 2 0 114 0v1a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-1a2 2 0 100 4h1a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-1a2 2 0 10-4 0v1a1 1 0 01-1 1H7a1 1 0 01-1-1v-3a1 1 0 00-1-1H4a2 2 0 110-4h1a1 1 0 001-1V7a1 1 0 011-1h3a1 1 0 001-1V4z",
  },
  {
    title: "Resultados",
    desc: "Memória de cálculo, OrçaFacil, laudos e cronograma com rastreabilidade de decisão.",
    icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
  },
] as const;

const MODULES = [
  {
    title: "Chat IA",
    desc: "Respostas técnicas por disciplina, anexos, export memória/TRD e croqui estrutural.",
    icon: "M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z",
  },
  {
    title: "Orçamento",
    desc: "PPD, BDI edital, Lançar Preços, exports oficiais e bases SINAPI/SICRO.",
    icon: "M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z",
  },
  {
    title: "OrçaFacil",
    desc: "Takeoff assistido por visão e Gemini, montagem automática da planilha modelo.",
    icon: "M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z",
  },
  {
    title: "Laudos de Vistoria",
    desc: "Croqui, ART, PAdES e layout institucional com sumário paginado.",
    icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
  },
  {
    title: "Projetos & Vision",
    desc: "Ingestão multi-formato, revisão NCs, OCR/BIM/CAD e análise visual.",
    icon: "M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10",
  },
  {
    title: "Knowledge & Console",
    desc: "RAG NBR em FAISS, Norm Packs, importação em lote e transparência operacional.",
    icon: "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253",
  },
] as const;

const CASES = [
  {
    metric: "−40%",
    label: "tempo de orçamento",
    title: "Edificação pública · AM",
    text: "Equipe usou OrçaFacil + SINAPI para montar a planilha a partir de pranchas e fotos de campo, com revisão humana só nos itens needs_match.",
  },
  {
    metric: "14k+",
    label: "chunks NBR indexados",
    title: "RAG normativo em produção",
    text: "Consultas de estruturas e hidráulica citam NBR com contexto recuperado — menos alucinação de tabela e mais rastreabilidade.",
  },
  {
    metric: "1 fluxo",
    label: "vistoria → PDF/ART",
    title: "Laudos institucionais",
    text: "Do registro fotográfico ao documento com sumário paginado, croqui e assinatura PAdES no padrão da empresa.",
  },
] as const;

function Icon({ d, className }: { d: string; className?: string }) {
  return (
    <svg className={cn("h-5 w-5", className)} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={d} />
    </svg>
  );
}

function LogoMark({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const box =
    size === "lg" ? "h-14 w-14 p-[2.5px]" : size === "sm" ? "h-9 w-9 p-[2px]" : "h-11 w-11 p-[2px]";
  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-sky-400/90 via-brand-500 to-brand-700 shadow-brand-sm ring-1 ring-sky-300/30",
        box
      )}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/logo.png" alt="" className="h-full w-full rounded-full bg-white object-cover" />
    </div>
  );
}

function LandingLoginCard() {
  const { login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/chat";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(username.trim(), password);
      if (typeof window !== "undefined" && !remember) {
        // sessão segue no fluxo atual do AuthContext; flag só UX
      }
      router.replace(next.startsWith("/") ? next : "/chat");
    } catch (err) {
      setError(formatApiError(err instanceof Error ? err.message : String(err)));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      id="login"
      className="landing-login relative w-full max-w-md overflow-hidden rounded-2xl border border-white/10 bg-slate-950/70 p-6 shadow-glow backdrop-blur-xl sm:p-8"
    >
      <div className="pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full bg-brand-500/20 blur-3xl" />
      <div className="relative mb-6 flex items-center gap-3">
        <LogoMark size="md" />
        <div>
          <p className="text-lg font-semibold text-white">Acesse sua conta</p>
          <p className="text-xs text-slate-400">Ambiente controlado da equipe</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="relative space-y-4">
        <div>
          <label className="mb-1.5 block text-xs font-medium text-slate-400">E-mail ou usuário</label>
          <div className="relative">
            <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-500">
              <Icon d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </span>
            <input
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="seu.usuario"
              className="w-full rounded-xl border border-white/10 bg-slate-900/80 py-2.5 pl-10 pr-3 text-sm text-slate-100 placeholder:text-slate-600 focus:border-brand-500/50 focus:outline-none focus:ring-1 focus:ring-brand-500/30"
              required
            />
          </div>
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-medium text-slate-400">Senha</label>
          <div className="relative">
            <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-500">
              <Icon d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </span>
            <input
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full rounded-xl border border-white/10 bg-slate-900/80 py-2.5 pl-10 pr-10 text-sm text-slate-100 placeholder:text-slate-600 focus:border-brand-500/50 focus:outline-none focus:ring-1 focus:ring-brand-500/30"
              required
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              className="absolute inset-y-0 right-2 flex items-center px-2 text-slate-500 hover:text-slate-300"
              title={showPassword ? "Ocultar senha" : "Mostrar senha"}
            >
              <Icon
                d={
                  showPassword
                    ? "M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"
                    : "M15 12a3 3 0 11-6 0 3 3 0 016 0z M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                }
              />
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 text-xs">
          <label className="flex cursor-pointer items-center gap-2 text-slate-400">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="rounded border-white/20 bg-slate-900 text-brand-500 focus:ring-brand-500/40"
            />
            Lembrar-me
          </label>
          <a href="#contato" className="text-brand-400 hover:text-brand-300">
            Precisa de acesso?
          </a>
        </div>

        {error ? (
          <p className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-300">
            {error}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-xl bg-gradient-to-r from-brand-600 to-sky-500 px-4 py-2.5 text-sm font-semibold text-white shadow-brand-sm transition hover:brightness-110 disabled:opacity-60"
        >
          {submitting ? "Entrando…" : "Entrar"}
        </button>
      </form>

      <p className="relative mt-5 text-center text-xs text-slate-500">
        Não tem uma conta?{" "}
        <a href="#contato" className="font-medium text-brand-400 hover:text-brand-300">
          Fale conosco
        </a>
      </p>
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="landing-root relative min-h-dvh overflow-x-hidden bg-[#07090f] text-slate-100">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-32 top-0 h-[28rem] w-[28rem] rounded-full bg-brand-600/20 blur-[120px]" />
        <div className="absolute right-0 top-40 h-[22rem] w-[22rem] rounded-full bg-sky-500/10 blur-[100px]" />
        <div
          className="absolute inset-0 opacity-[0.35]"
          style={{
            backgroundImage:
              "radial-gradient(rgba(56,189,248,0.12) 1px, transparent 1px)",
            backgroundSize: "28px 28px",
          }}
        />
      </div>

      <header className="relative z-20 border-b border-white/5 bg-[#07090f]/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <a href="#topo" className="flex min-w-0 items-center gap-2.5">
            <LogoMark size="sm" />
            <span className="truncate text-sm font-semibold tracking-wide text-white sm:text-base">
              IA Server Santos
            </span>
          </a>
          <nav className="hidden items-center gap-6 text-sm text-slate-400 lg:flex">
            {NAV.map((item) => (
              <a key={item.href} href={item.href} className="transition hover:text-white">
                {item.label}
              </a>
            ))}
          </nav>
          <a
            href="#login"
            className="rounded-xl border border-brand-500/40 px-3.5 py-1.5 text-sm font-medium text-brand-300 transition hover:border-brand-400 hover:bg-brand-500/10 hover:text-white"
          >
            Login
          </a>
        </div>
      </header>

      <main id="topo" className="relative z-10">
        {/* Hero */}
        <section className="mx-auto max-w-6xl px-4 pb-16 pt-4 sm:px-6 sm:pt-6 lg:pb-24 lg:pt-8">
          <div className="grid gap-10 lg:grid-cols-2 lg:items-start lg:gap-12">
            <div className="landing-fade-up">
              <p className="mb-4 text-[11px] font-semibold uppercase tracking-[0.22em] text-brand-400">
                Inteligência artificial · dados · soluções
              </p>
              <h1 className="max-w-xl text-4xl font-bold leading-[1.1] tracking-tight text-white sm:text-5xl lg:text-[3.25rem]">
                Inteligência que constrói{" "}
                <span className="bg-gradient-to-r from-brand-300 to-sky-400 bg-clip-text text-transparent">
                  soluções
                </span>
                .
              </h1>
              <p className="mt-5 max-w-lg text-base leading-relaxed text-slate-400 sm:text-lg">
                Plataforma SaaS de engenharia civil multiagente: chat técnico, orçamento SINAPI/SICRO,
                laudos, projetos e RAG normativo — do rascunho à entrega documentada.
              </p>

              <ul className="mt-8 grid gap-3 sm:grid-cols-3">
                {PILLARS.map((p) => (
                  <li
                    key={p.title}
                    className="rounded-xl border border-white/5 bg-white/[0.03] px-3 py-3"
                  >
                    <div className="mb-2 flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500/15 text-brand-300">
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        {p.icon}
                      </svg>
                    </div>
                    <p className="text-xs font-semibold text-slate-200">{p.title}</p>
                    <p className="mt-1 text-[11px] leading-snug text-slate-500">{p.desc}</p>
                  </li>
                ))}
              </ul>

              <div className="mt-8 flex flex-wrap gap-3">
                <a
                  href="#modulos"
                  className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-brand-600 to-sky-500 px-5 py-2.5 text-sm font-semibold text-white shadow-brand-sm transition hover:brightness-110"
                >
                  Conheça os módulos
                  <Icon d="M13 7l5 5m0 0l-5 5m5-5H6" className="h-4 w-4" />
                </a>
                <a
                  href="#casos"
                  className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/5 px-5 py-2.5 text-sm font-medium text-slate-200 transition hover:border-brand-500/40 hover:text-white"
                >
                  <span className="flex h-5 w-5 items-center justify-center rounded-full border border-brand-400/50 text-brand-300">
                    <Icon d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" className="h-3 w-3" />
                  </span>
                  Ver casos de sucesso
                </a>
              </div>
            </div>

            <div className="landing-fade-up-delay flex justify-center lg:sticky lg:top-24 lg:justify-end lg:self-start">
              <LandingLoginCard />
            </div>
          </div>

          <div className="landing-fade-up mt-10 grid gap-4 lg:mt-12 lg:grid-cols-2 lg:items-start">
            <QuadraticStreamDemo />
            <BeamReactionsStreamDemo />
          </div>
        </section>

        {/* Benefícios */}
        <section id="recursos" className="border-t border-white/5 bg-black/20 py-16 sm:py-20">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <h2 className="max-w-2xl text-2xl font-bold tracking-tight text-white sm:text-3xl">
              Tecnologia que transforma dados em decisões inteligentes.
            </h2>
            <p className="mt-3 max-w-2xl text-sm text-slate-400 sm:text-base">
              Do agente de disciplina ao export institucional — um único ambiente para a equipe de
              engenharia.
            </p>
            <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {BENEFITS.map((b) => (
                <article
                  key={b.title}
                  className="group rounded-2xl border border-white/5 bg-surface-card/80 p-5 transition hover:border-brand-500/35 hover:bg-surface-elevated"
                >
                  <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500/10 text-brand-400 transition group-hover:bg-brand-500/20">
                    <Icon d={b.icon} />
                  </div>
                  <h3 className="text-base font-semibold text-white">{b.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-400">{b.desc}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* Módulos */}
        <section id="modulos" className="py-16 sm:py-20">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-brand-400">
                  Módulos
                </p>
                <h2 className="mt-2 text-2xl font-bold text-white sm:text-3xl">
                  Soluções completas para sua gestão.
                </h2>
              </div>
              <a
                href="#login"
                className="text-sm font-medium text-brand-400 hover:text-brand-300"
              >
                Entrar para explorar →
              </a>
            </div>
            <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {MODULES.map((m) => (
                <article
                  key={m.title}
                  className="rounded-2xl border border-white/5 bg-white/[0.03] p-5 transition hover:border-brand-500/30 hover:bg-white/[0.05]"
                >
                  <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl border border-brand-500/20 bg-brand-500/10 text-brand-300">
                    <Icon d={m.icon} />
                  </div>
                  <h3 className="text-base font-semibold text-white">{m.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-400">{m.desc}</p>
                </article>
              ))}
            </div>
            <div className="mt-8 flex justify-center">
              <a
                href="#login"
                className="rounded-xl border border-brand-500/40 px-6 py-2.5 text-sm font-medium text-brand-300 transition hover:bg-brand-500/10 hover:text-white"
              >
                Ver todos os módulos no sistema
              </a>
            </div>
          </div>
        </section>

        {/* Casos */}
        <section id="casos" className="border-t border-white/5 bg-gradient-to-b from-brand-600/10 to-transparent py-16 sm:py-20">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-brand-400">
              Casos de sucesso
            </p>
            <h2 className="mt-2 max-w-xl text-2xl font-bold text-white sm:text-3xl">
              Resultados que a equipe já entrega no dia a dia.
            </h2>
            <div className="mt-10 grid gap-5 lg:grid-cols-3">
              {CASES.map((c) => (
                <article
                  key={c.title}
                  className="flex flex-col rounded-2xl border border-white/10 bg-slate-950/50 p-6 backdrop-blur"
                >
                  <p className="text-3xl font-bold tracking-tight text-brand-300">{c.metric}</p>
                  <p className="mt-1 text-xs font-medium uppercase tracking-wide text-slate-500">
                    {c.label}
                  </p>
                  <h3 className="mt-4 text-base font-semibold text-white">{c.title}</h3>
                  <p className="mt-2 flex-1 text-sm leading-relaxed text-slate-400">{c.text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* Contato / CTA */}
        <section id="contato" className="py-16 sm:py-20">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="overflow-hidden rounded-3xl border border-brand-500/25 bg-gradient-to-br from-brand-600/20 via-slate-950 to-slate-950 p-8 sm:p-10">
              <div className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
                <div>
                  <h2 className="text-2xl font-bold text-white sm:text-3xl">
                    Pronto para acelerar a engenharia com IA?
                  </h2>
                  <p className="mt-3 max-w-xl text-sm text-slate-300 sm:text-base">
                    Solicite acesso à equipe ou entre com suas credenciais. O login fica no topo —
                    a exploração começa em segundos.
                  </p>
                </div>
                <div className="flex flex-col gap-3 sm:flex-row lg:flex-col lg:items-stretch">
                  <a
                    href="#login"
                    className="inline-flex items-center justify-center rounded-xl bg-gradient-to-r from-brand-600 to-sky-500 px-5 py-3 text-sm font-semibold text-white shadow-brand-sm transition hover:brightness-110"
                  >
                    Ir para o login
                  </a>
                  <a
                    href="mailto:contato@iaserversantos.local"
                    className="inline-flex items-center justify-center rounded-xl border border-white/15 px-5 py-3 text-sm font-medium text-slate-200 transition hover:border-brand-400/40 hover:text-white"
                  >
                    Fale conosco
                  </a>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="relative z-10 border-t border-white/5 bg-black/40">
        <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-2 lg:grid-cols-4">
          <div className="lg:col-span-1">
            <div className="flex items-center gap-2.5">
              <LogoMark size="sm" />
              <span className="font-semibold text-white">IA Server Santos</span>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-slate-500">
              SaaS de engenharia civil multiagente — orçamento, normas, laudos e projetos em um só
              lugar.
            </p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Links rápidos
            </p>
            <ul className="mt-3 space-y-2 text-sm text-slate-500">
              {NAV.map((n) => (
                <li key={n.href}>
                  <a href={n.href} className="hover:text-brand-300">
                    {n.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Suporte</p>
            <ul className="mt-3 space-y-2 text-sm text-slate-500">
              <li>
                <a href="#login" className="hover:text-brand-300">
                  Acesso ao sistema
                </a>
              </li>
              <li>
                <a href="#contato" className="hover:text-brand-300">
                  Solicitar conta
                </a>
              </li>
              <li>
                <a href="mailto:contato@iaserversantos.local" className="hover:text-brand-300">
                  E-mail
                </a>
              </li>
            </ul>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <p className="text-sm font-semibold text-white">Vamos conversar?</p>
            <p className="mt-1 text-xs text-slate-500">
              Onboarding da equipe e demonstração dos módulos.
            </p>
            <a
              href="#contato"
              className="mt-4 inline-flex w-full items-center justify-center rounded-xl bg-brand-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-500"
            >
              Fale conosco
            </a>
          </div>
        </div>
        <div className="border-t border-white/5 py-4">
          <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 text-xs text-slate-600 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <p>© {new Date().getFullYear()} IA Server Santos. Todos os direitos reservados.</p>
            <p>Engenharia · IA · Entrega documentada</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
