import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageSquare, Terminal, Globe, Code2 } from 'lucide-react';
import { SectionHeader } from '../components/SectionHeader';

const chatMessages = [
  { role: 'user', text: 'Crie uma landing page React com Tailwind' },
  { role: 'assistant', text: 'Criando componentes Hero, Features e FAQ...' },
  { role: 'tool', text: 'create_file → src/sections/Hero.tsx ✓' },
  { role: 'tool', text: 'create_file → src/sections/Features.tsx ✓' },
];

const codeLines = [
  'export function Hero() {',
  '  return (',
  '    <section className="hero">',
  '      <h1>Cursor Local</h1>',
  '    </section>',
  '  );',
  '}',
];

const terminalLines = [
  '$ npm install',
  'added 248 packages',
  '$ npm run dev',
  'VITE ready → localhost:5174',
];

export function Demo() {
  const [chatIdx, setChatIdx] = useState(0);
  const [codeIdx, setCodeIdx] = useState(0);
  const [termIdx, setTermIdx] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setChatIdx((i) => (i + 1) % (chatMessages.length + 1)), 2000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const t = setInterval(() => setCodeIdx((i) => Math.min(i + 1, codeLines.length)), 800);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const t = setInterval(() => setTermIdx((i) => Math.min(i + 1, terminalLines.length)), 1200);
    return () => clearInterval(t);
  }, []);

  return (
    <section id="demo" className="border-y border-border bg-surface-elevated py-24 sm:py-32">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeader label="Demonstração" title="Veja a magia acontecer em tempo real" />
        <div className="mt-16 grid gap-6 lg:grid-cols-2">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="rounded-2xl border border-border bg-surface-card overflow-hidden"
          >
            <div className="flex items-center gap-2 border-b border-border px-4 py-2 text-xs text-zinc-500">
              <MessageSquare size={14} /> Chat IA
            </div>
            <div className="space-y-3 p-4 min-h-[200px]">
              <AnimatePresence>
                {chatMessages.slice(0, chatIdx).map((m, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: m.role === 'user' ? 20 : -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    className={`rounded-lg p-3 text-sm ${
                      m.role === 'user' ? 'ml-8 bg-brand-500/10 text-brand-300' :
                      m.role === 'tool' ? 'bg-green-500/10 text-green-400 font-mono text-xs' :
                      'mr-8 bg-zinc-800 text-zinc-300'
                    }`}
                  >
                    {m.text}
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
            className="rounded-2xl border border-border bg-surface-card overflow-hidden"
          >
            <div className="flex items-center gap-2 border-b border-border px-4 py-2 text-xs text-zinc-500">
              <Code2 size={14} /> Código gerado
            </div>
            <pre className="p-4 font-mono text-xs leading-relaxed text-zinc-300 min-h-[200px]">
              {codeLines.slice(0, codeIdx).map((line, i) => (
                <motion.div key={i} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  {line}
                </motion.div>
              ))}
            </pre>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2 }}
            className="rounded-2xl border border-border bg-surface-card overflow-hidden"
          >
            <div className="flex items-center gap-2 border-b border-border px-4 py-2 text-xs text-zinc-500">
              <Terminal size={14} /> Terminal
            </div>
            <div className="space-y-1 p-4 font-mono text-xs min-h-[200px]">
              {terminalLines.slice(0, termIdx).map((line, i) => (
                <motion.div key={i} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-green-400">
                  {line}
                </motion.div>
              ))}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.3 }}
            className="rounded-2xl border border-border bg-surface-card overflow-hidden"
          >
            <div className="flex items-center gap-2 border-b border-border px-4 py-2 text-xs text-zinc-500">
              <Globe size={14} /> Preview
            </div>
            <div className="flex min-h-[200px] items-center justify-center bg-gradient-to-br from-brand-500/10 to-purple-500/10 p-8">
              <motion.div
                animate={{ scale: [1, 1.02, 1] }}
                transition={{ repeat: Infinity, duration: 3 }}
                className="text-center"
              >
                <div className="text-2xl font-bold text-white">Cursor Local</div>
                <div className="mt-2 text-sm text-zinc-400">localhost:5174</div>
              </motion.div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
