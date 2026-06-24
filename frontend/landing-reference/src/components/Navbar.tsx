import { Code2 } from 'lucide-react';
import { Button } from './Button';
import { useScrollTo } from '../hooks/useScrollTo';

const links = [
  { label: 'Recursos', href: 'features' },
  { label: 'Como Funciona', href: 'how-it-works' },
  { label: 'Demonstração', href: 'demo' },
  { label: 'FAQ', href: 'faq' },
];

export function Navbar() {
  const scrollTo = useScrollTo();

  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b border-white/5 bg-surface/80 backdrop-blur-xl">
      <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500">
            <Code2 size={18} className="text-white" />
          </div>
          <span className="font-semibold text-white">Cursor Local</span>
        </div>
        <div className="hidden items-center gap-6 md:flex">
          {links.map((l) => (
            <button
              key={l.href}
              onClick={() => scrollTo(l.href)}
              className="text-sm text-zinc-400 transition hover:text-white"
            >
              {l.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" className="hidden sm:inline-flex" onClick={() => scrollTo('demo')}>
            Demo
          </Button>
          <Button onClick={() => scrollTo('cta')}>Começar Agora</Button>
        </div>
      </nav>
    </header>
  );
}
