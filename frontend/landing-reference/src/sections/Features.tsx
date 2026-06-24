import { motion } from 'framer-motion';
import {
  Cpu, Sparkles, Bot, Terminal, Globe, Brain,
} from 'lucide-react';
import { SectionHeader } from '../components/SectionHeader';
import type { LucideIcon } from 'lucide-react';

interface Feature {
  icon: LucideIcon;
  title: string;
  description: string;
}

const features: Feature[] = [
  { icon: Cpu, title: 'IA Local', description: 'Execute qwen3, deepseek-coder e gemma4 via Ollama sem enviar código para a nuvem.' },
  { icon: Sparkles, title: 'Edição Inteligente', description: 'Monaco Editor com syntax highlight, auto save, tabs múltiplas e diff viewer.' },
  { icon: Bot, title: 'Agentes Autônomos', description: 'Agentes que leem, criam, editam e refatoram arquivos automaticamente no seu workspace.' },
  { icon: Terminal, title: 'Terminal Integrado', description: 'Execute comandos, veja logs e interrompa processos sem sair do ambiente.' },
  { icon: Globe, title: 'Preview em Tempo Real', description: 'Detecte apps web, rode npm run dev e visualize o resultado em iframe integrado.' },
  { icon: Brain, title: 'Memória Persistente', description: 'RAG local com ChromaDB indexa seu projeto para contexto automático nas conversas.' },
];

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.1 } },
};

const item = {
  hidden: { opacity: 0, y: 24 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5 } },
};

export function Features() {
  return (
    <section id="features" className="py-24 sm:py-32">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeader
          label="Recursos"
          title="Tudo que você precisa para desenvolver com IA privada"
          subtitle="Um ambiente completo inspirado no Cursor, executado na sua infraestrutura."
        />
        <motion.div
          variants={container}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: '-60px' }}
          className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3"
        >
          {features.map((f) => (
            <motion.div
              key={f.title}
              variants={item}
              className="group rounded-2xl border border-border bg-surface-card p-6 transition hover:border-brand-500/30 hover:bg-surface-elevated"
            >
              <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-brand-500/10 text-brand-400 transition group-hover:bg-brand-500/20">
                <f.icon size={22} />
              </div>
              <h3 className="text-lg font-semibold text-white">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-zinc-400">{f.description}</p>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
