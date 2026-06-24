import { motion } from 'framer-motion';
import { Download, ArrowRight } from 'lucide-react';
import { Button } from '../components/Button';

export function CTA() {
  return (
    <section id="cta" className="py-24 sm:py-32">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          className="relative overflow-hidden rounded-3xl border border-brand-500/30 bg-gradient-to-br from-brand-500/10 via-surface-card to-purple-500/10 px-8 py-16 text-center sm:px-16"
        >
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(14,165,233,0.15),transparent_70%)]" />
          <div className="relative">
            <h2 className="text-3xl font-bold text-white sm:text-4xl">
              Pronto para ter sua própria IA de desenvolvimento?
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-zinc-400">
              Instale o Cursor Local, conecte o Ollama e comece a construir com privacidade total.
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Button className="px-8 py-3 text-base">
                <Download size={18} /> Baixar Agora
              </Button>
              <Button variant="secondary" className="px-8 py-3 text-base">
                Documentação <ArrowRight size={18} />
              </Button>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
