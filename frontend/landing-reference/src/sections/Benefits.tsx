import { motion } from 'framer-motion';
import { Check, X } from 'lucide-react';
import { SectionHeader } from '../components/SectionHeader';

const ours = [
  'Dados privados',
  'Sem custos por API',
  'Funciona offline',
  'Modelos personalizados',
  'Controle total',
];

const theirs = [
  'Dependência de nuvem',
  'Custos recorrentes',
  'Limitações de uso',
];

export function Benefits() {
  return (
    <section className="py-24 sm:py-32">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeader
          label="Benefícios"
          title="Por que escolher Cursor Local?"
          subtitle="Compare a liberdade de rodar IA na sua máquina com ferramentas tradicionais baseadas em nuvem."
        />
        <div className="mt-16 grid gap-8 md:grid-cols-2">
          <motion.div
            initial={{ opacity: 0, x: -30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="rounded-2xl border border-brand-500/30 bg-brand-500/5 p-8"
          >
            <h3 className="text-xl font-bold text-white">Cursor Local</h3>
            <ul className="mt-6 space-y-4">
              {ours.map((b) => (
                <li key={b} className="flex items-center gap-3 text-zinc-300">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-green-500/20 text-green-400">
                    <Check size={14} />
                  </span>
                  {b}
                </li>
              ))}
            </ul>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, x: 30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="rounded-2xl border border-border bg-surface-card p-8"
          >
            <h3 className="text-xl font-bold text-zinc-400">Ferramentas tradicionais</h3>
            <ul className="mt-6 space-y-4">
              {theirs.map((b) => (
                <li key={b} className="flex items-center gap-3 text-zinc-500">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-red-500/10 text-red-400">
                    <X size={14} />
                  </span>
                  {b}
                </li>
              ))}
            </ul>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
