import { motion } from 'framer-motion';
import { Star } from 'lucide-react';
import { SectionHeader } from '../components/SectionHeader';

const testimonials = [
  {
    name: 'Ana Ribeiro',
    role: 'Tech Lead · Fintech',
    text: 'Finalmente consigo usar IA no código sem enviar dados sensíveis para servidores externos. O Cursor Local transformou nosso fluxo de desenvolvimento.',
  },
  {
    name: 'Marcos Oliveira',
    role: 'Desenvolvedor Full Stack',
    text: 'Os agentes autônomos criaram um projeto inteiro enquanto eu tomava café. Integração com Ollama impecável e zero custo por token.',
  },
  {
    name: 'Carla Mendes',
    role: 'CTO · Startup de Saúde',
    text: 'Privacidade era requisito legal para nós. Com modelos locais e RAG no ChromaDB, temos IA poderosa mantendo compliance total.',
  },
];

export function Testimonials() {
  return (
    <section className="py-24 sm:py-32">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeader label="Depoimentos" title="Desenvolvedores que já confiam" />
        <div className="mt-16 grid gap-8 md:grid-cols-3">
          {testimonials.map((t, i) => (
            <motion.blockquote
              key={t.name}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              className="rounded-2xl border border-border bg-surface-card p-6"
            >
              <div className="flex gap-1 text-yellow-400">
                {Array.from({ length: 5 }).map((_, j) => (
                  <Star key={j} size={14} fill="currentColor" />
                ))}
              </div>
              <p className="mt-4 text-sm leading-relaxed text-zinc-300">"{t.text}"</p>
              <footer className="mt-6 border-t border-border pt-4">
                <div className="font-semibold text-white">{t.name}</div>
                <div className="text-xs text-zinc-500">{t.role}</div>
              </footer>
            </motion.blockquote>
          ))}
        </div>
      </div>
    </section>
  );
}
