import { motion } from 'framer-motion';
import { Plug, FolderOpen, MessageCircle, Wand2 } from 'lucide-react';
import { SectionHeader } from '../components/SectionHeader';
import type { LucideIcon } from 'lucide-react';

const steps: { step: number; icon: LucideIcon; title: string; description: string }[] = [
  { step: 1, icon: Plug, title: 'Conecte seus modelos Ollama', description: 'Instale o Ollama, baixe qwen3-coder ou deepseek-coder e conecte em um clique.' },
  { step: 2, icon: FolderOpen, title: 'Abra seu projeto', description: 'Crie um workspace, navegue arquivos, faça upload e organize seu código.' },
  { step: 3, icon: MessageCircle, title: 'Converse com a IA', description: 'Use o chat com streaming, histórico de conversas e contexto automático do projeto.' },
  { step: 4, icon: Wand2, title: 'Veja o código sendo criado', description: 'Ative o modo agente e observe arquivos sendo criados, editados e testados automaticamente.' },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="border-y border-border bg-surface-elevated py-24 sm:py-32">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeader label="Como Funciona" title="Do zero ao projeto em 4 passos" />
        <div className="relative mt-16">
          <div className="absolute left-8 top-0 hidden h-full w-px bg-gradient-to-b from-brand-500/50 via-brand-500/20 to-transparent md:block" />
          <div className="space-y-12">
            {steps.map((s, i) => (
              <motion.div
                key={s.step}
                initial={{ opacity: 0, x: -30 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.15 }}
                className="relative flex gap-6 md:gap-10"
              >
                <div className="relative z-10 flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl border border-brand-500/30 bg-brand-500/10">
                  <s.icon size={28} className="text-brand-400" />
                </div>
                <div className="pt-2">
                  <span className="text-xs font-medium uppercase tracking-wider text-brand-400">Etapa {s.step}</span>
                  <h3 className="mt-1 text-xl font-semibold text-white">{s.title}</h3>
                  <p className="mt-2 max-w-lg text-zinc-400">{s.description}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
