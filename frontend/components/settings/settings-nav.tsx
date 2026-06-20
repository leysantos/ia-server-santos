import type { ReactNode } from "react";

export type SettingsModuleId =
  | "overview"
  | "document-types"
  | "imports"
  | "catalog"
  | "indexing";

export interface SettingsModule {
  id: SettingsModuleId;
  href: string;
  label: string;
  description: string;
  icon: ReactNode;
}

function Icon({ d }: { d: string }) {
  return (
    <svg className="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={d} />
    </svg>
  );
}

/** Registro central — adicione novos submódulos aqui. */
export const SETTINGS_MODULES: SettingsModule[] = [
  {
    id: "overview",
    href: "/settings",
    label: "Visão geral",
    description: "Resumo da base de conhecimento e índices FAISS",
    icon: <Icon d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />,
  },
  {
    id: "document-types",
    href: "/settings/document-types",
    label: "Tipos de documento",
    description: "Cadastro de combinações nome + disciplina + tipo de conteúdo",
    icon: <Icon d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A2 2 0 013 12V7a4 4 0 014-4z" />,
  },
  {
    id: "imports",
    href: "/settings/imports",
    label: "Importações",
    description: "Upload de arquivos e importação em lote de sites públicos",
    icon: <Icon d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />,
  },
  {
    id: "catalog",
    href: "/settings/catalog",
    label: "Catálogo",
    description: "Documentos ingeridos, edição e bases de preço ativas",
    icon: <Icon d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />,
  },
  {
    id: "indexing",
    href: "/settings/indexing",
    label: "Indexação FAISS",
    description: "Reindexação manual quando a indexação automática falhar",
    icon: <Icon d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />,
  },
];

export function resolveSettingsModule(pathname: string): SettingsModule {
  const exact = SETTINGS_MODULES.find((m) => m.href === pathname);
  if (exact) return exact;
  const nested = SETTINGS_MODULES.filter((m) => m.href !== "/settings").find((m) =>
    pathname.startsWith(m.href)
  );
  return nested ?? SETTINGS_MODULES[0];
}
