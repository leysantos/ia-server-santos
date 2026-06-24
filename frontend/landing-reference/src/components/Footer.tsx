import { Code2, GitBranch } from 'lucide-react';

export function Footer() {
  return (
    <footer className="border-t border-border bg-surface-elevated py-12">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 px-4 sm:flex-row sm:px-6">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500">
            <Code2 size={18} className="text-white" />
          </div>
          <span className="font-semibold">Cursor Local</span>
        </div>
        <p className="text-sm text-zinc-500">© {new Date().getFullYear()} Cursor Local. Todos os direitos reservados.</p>
        <a href="https://github.com" className="flex items-center gap-2 text-sm text-zinc-400 hover:text-white">
          <GitBranch size={16} /> GitHub
        </a>
      </div>
    </footer>
  );
}
