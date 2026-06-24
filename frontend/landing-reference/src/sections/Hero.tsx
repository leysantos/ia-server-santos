import { motion } from 'framer-motion';
import { ArrowRight, Play, Terminal, MessageSquare, Globe, FileCode } from 'lucide-react';
import { Button } from '../components/Button';
import { useScrollTo } from '../hooks/useScrollTo';

export function Hero() {
  const scrollTo = useScrollTo();

  return (
    <section className="relative overflow-hidden pt-32 pb-20 sm:pt-40 sm:pb-28">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-1/2 top-0 h-[500px] w-[800px] -translate-x-1/2 rounded-full bg-brand-500/10 blur-[120px]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(14,165,233,0.08),transparent_50%)]" />
      </div>

      <div className="relative mx-auto max-w-6xl px-4 sm:px-6">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mx-auto max-w-3xl text-center"
        >
          <span className="mb-6 inline-flex items-center gap-2 rounded-full border border-brand-500/30 bg-brand-500/10 px-4 py-1.5 text-sm text-brand-400">
            <span className="h-1.5 w-1.5 rounded-full bg-brand-400 animate-pulse" />
            Powered by Ollama · 100% Local
          </span>
          <h1 className="text-4xl font-extrabold tracking-tight sm:text-6xl lg:text-7xl">
            <span className="gradient-text">Seu Cursor Privado</span>
            <br />
            <span className="text-white">Rodando Localmente</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-zinc-400 sm:text-xl">
            Crie, edite e execute projetos inteiros utilizando modelos locais com total privacidade.
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Button className="px-8 py-3 text-base" onClick={() => scrollTo('cta')}>
              Começar Agora <ArrowRight size={18} />
            </Button>
            <Button variant="secondary" className="px-8 py-3 text-base" onClick={() => scrollTo('demo')}>
              <Play size={18} /> Ver Demonstração
            </Button>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 60 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.3 }}
          className="relative mx-auto mt-16 max-w-5xl"
        >
          <div className="gradient-border glow rounded-2xl p-[1px]">
            <div className="overflow-hidden rounded-2xl bg-surface-card">
              <div className="flex items-center gap-2 border-b border-border px-4 py-3">
                <div className="h-3 w-3 rounded-full bg-red-500/80" />
                <div className="h-3 w-3 rounded-full bg-yellow-500/80" />
                <div className="h-3 w-3 rounded-full bg-green-500/80" />
                <span className="ml-2 text-xs text-zinc-500">cursor-local — workspace</span>
              </div>
              <div className="grid md:grid-cols-12">
                <div className="border-r border-border p-3 md:col-span-2">
                  <div className="space-y-2 text-xs text-zinc-500">
                    <div className="flex items-center gap-1.5 text-brand-400"><FileCode size={12} /> app.py</div>
                    <div className="pl-4">models/</div>
                    <div className="pl-4">tests/</div>
                  </div>
                </div>
                <div className="border-r border-border p-4 font-mono text-xs leading-relaxed md:col-span-5">
                  <div className="text-purple-400">from <span className="text-zinc-300">fastapi</span> import FastAPI</div>
                  <div className="mt-2 text-zinc-300">app = FastAPI()</div>
                  <div className="mt-2 text-yellow-300">@app.get<span className="text-zinc-300">("/health")</span></div>
                  <div className="text-zinc-300">async def health():</div>
                  <div className="pl-4 text-green-400">return {"{"}"status": "ok"{"}"}</div>
                </div>
                <div className="border-r border-border p-3 md:col-span-3">
                  <div className="mb-2 flex items-center gap-1 text-xs text-zinc-500"><MessageSquare size={12} /> Chat IA</div>
                  <div className="space-y-2 text-xs">
                    <div className="rounded-lg bg-brand-500/10 p-2 text-brand-300">Crie um endpoint /health</div>
                    <div className="rounded-lg bg-zinc-800 p-2 text-zinc-400">Arquivo app.py criado ✓</div>
                  </div>
                </div>
                <div className="p-3 md:col-span-2">
                  <div className="mb-2 flex items-center gap-1 text-xs text-zinc-500"><Terminal size={12} /> Terminal</div>
                  <div className="font-mono text-[10px] text-green-400">$ uvicorn app:app</div>
                  <div className="mt-2 flex items-center gap-1 text-xs text-zinc-500"><Globe size={12} /> Preview</div>
                  <div className="mt-1 rounded bg-white/5 p-1 text-[10px] text-zinc-400">localhost:8080</div>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
