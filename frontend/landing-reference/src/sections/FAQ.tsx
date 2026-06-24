import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown } from 'lucide-react';
import { SectionHeader } from '../components/SectionHeader';
import { cn } from '../utils/cn';

const faqs = [
  { q: 'O que é o Cursor Local?', a: 'Cursor Local é uma plataforma de IA para programação que roda inteiramente na sua infraestrutura, utilizando modelos locais via Ollama. Oferece editor, chat, agentes, terminal e preview integrados.' },
  { q: 'Preciso de internet para usar?', a: 'Após instalar os modelos Ollama, você pode desenvolver offline. Apenas o download inicial dos modelos requer conexão.' },
  { q: 'Quais modelos são suportados?', a: 'qwen3-coder, qwen3, deepseek-coder, gemma4 e qualquer modelo compatível com Ollama. Você escolhe qual usar no chat.' },
  { q: 'Meus dados ficam privados?', a: 'Sim. Todo o código permanece na sua máquina. Nenhum dado é enviado para APIs de terceiros. O sandbox impede acesso fora do workspace.' },
  { q: 'Como funciona o agente autônomo?', a: 'O agente usa ferramentas para ler, criar, editar, excluir e buscar arquivos no seu projeto. Basta ativar o Modo Agente e descrever o que deseja.' },
  { q: 'Posso usar com Docker?', a: 'Sim. O Cursor Local inclui docker-compose com frontend, backend, PostgreSQL e ChromaDB. Execute ./scripts/prod.sh para subir tudo.' },
  { q: 'Qual a diferença para o Cursor original?', a: 'O Cursor original usa modelos na nuvem. O Cursor Local roda modelos via Ollama na sua máquina, com controle total, sem custos por API e com privacidade completa.' },
  { q: 'É gratuito?', a: 'O software é open source. Você paga apenas pela sua infraestrutura (hardware/electricidade). Sem assinaturas ou cobrança por tokens.' },
];

export function FAQ() {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <section id="faq" className="border-t border-border bg-surface-elevated py-24 sm:py-32">
      <div className="mx-auto max-w-3xl px-4 sm:px-6">
        <SectionHeader label="FAQ" title="Perguntas frequentes" />
        <div className="mt-12 space-y-3">
          {faqs.map((faq, i) => (
            <div key={i} className="rounded-xl border border-border bg-surface-card overflow-hidden">
              <button
                className="flex w-full items-center justify-between px-5 py-4 text-left"
                onClick={() => setOpen(open === i ? null : i)}
              >
                <span className="font-medium text-white">{faq.q}</span>
                <ChevronDown size={18} className={cn('text-zinc-400 transition', open === i && 'rotate-180')} />
              </button>
              <AnimatePresence>
                {open === i && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.25 }}
                  >
                    <p className="border-t border-border px-5 py-4 text-sm leading-relaxed text-zinc-400">{faq.a}</p>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
