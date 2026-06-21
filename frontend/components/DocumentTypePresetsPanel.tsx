"use client";

import { useCallback, useState } from "react";
import { cn } from "@/lib/utils";
import { useActionDialog } from "@/hooks/useActionDialog";
import type { DocumentTypePreset, KnowledgeOptionsResponse } from "@/types/api";

interface DocumentTypePresetsPanelProps {
  options: KnowledgeOptionsResponse;
  embedded?: boolean;
  onCreate: (body: {
    id?: string;
    label: string;
    content_type: string;
    discipline: string;
    register_price_base?: boolean;
    register_budget_model?: boolean;
  }) => Promise<DocumentTypePreset>;
  onUpdate: (
    id: string,
    body: Partial<{
      label: string;
      content_type: string;
      discipline: string;
      register_price_base: boolean;
      register_budget_model: boolean;
    }>
  ) => Promise<DocumentTypePreset>;
  onDelete: (id: string) => Promise<DocumentTypePreset>;
  onRefresh: () => void;
}

const EMPTY_FORM = {
  id: "",
  label: "",
  content_type: "nbrs",
  discipline: "GERAL",
  register_price_base: false,
  register_budget_model: false,
};

function contentTypeLabel(options: KnowledgeOptionsResponse, value: string): string {
  return options.content_types.find((c) => c.value === value)?.label ?? value;
}

export default function DocumentTypePresetsPanel({
  options,
  embedded = false,
  onCreate,
  onUpdate,
  onDelete,
  onRefresh,
}: DocumentTypePresetsPanelProps) {
  const presets = options.document_type_presets ?? [];
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const { confirm, ActionDialogHost } = useActionDialog();

  const resetForm = useCallback(() => {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setError(null);
  }, []);

  const startEdit = (preset: DocumentTypePreset) => {
    setEditingId(preset.id);
    setForm({
      id: preset.id,
      label: preset.label,
      content_type: preset.content_type,
      discipline: preset.discipline,
      register_price_base: preset.register_price_base,
      register_budget_model: preset.register_budget_model,
    });
    setError(null);
    setSuccess(null);
  };

  const handleSubmit = async () => {
    if (!form.label.trim()) {
      setError("Informe o nome do tipo de documento.");
      return;
    }
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      if (editingId) {
        await onUpdate(editingId, {
          label: form.label.trim(),
          content_type: form.content_type,
          discipline: form.discipline,
          register_price_base: form.register_price_base,
          register_budget_model: form.register_budget_model,
        });
        setSuccess(`Tipo «${form.label.trim()}» atualizado.`);
      } else {
        await onCreate({
          ...(form.id.trim() ? { id: form.id.trim() } : {}),
          label: form.label.trim(),
          content_type: form.content_type,
          discipline: form.discipline,
          register_price_base: form.register_price_base,
          register_budget_model: form.register_budget_model,
        });
        setSuccess(`Tipo «${form.label.trim()}» cadastrado.`);
      }
      resetForm();
      onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar tipo de documento");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (preset: DocumentTypePreset) => {
    const ok = await confirm({
      title: "Excluir tipo de documento",
      message: `Excluir o tipo «${preset.label}»? Documentos já indexados não serão afetados.`,
      confirmLabel: "Excluir",
      destructive: true,
    });
    if (!ok) return;
    setDeletingId(preset.id);
    setError(null);
    setSuccess(null);
    try {
      await onDelete(preset.id);
      if (editingId === preset.id) resetForm();
      setSuccess(`Tipo «${preset.label}» removido.`);
      onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao excluir tipo de documento");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <section className={embedded ? "" : "rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800"}>
      {!embedded && (
        <>
          <h2 className="mb-1 text-base font-semibold text-white">Tipos de documento</h2>
          <p className="mb-4 text-sm text-slate-500">
            Cadastre combinações de <strong className="font-normal text-slate-400">nome</strong>,{" "}
            <strong className="font-normal text-slate-400">tipo de conteúdo</strong> (NBR, SINAPI, manual…)
            e <strong className="font-normal text-slate-400">disciplina</strong>. Elas aparecem nos
            formulários de upload e importação web — sem precisar alterar código.
          </p>
        </>
      )}

      {presets.length === 0 ? (
        <p className="mb-4 rounded-lg bg-slate-950/50 px-4 py-3 text-sm text-slate-500">
          Nenhum tipo cadastrado. Use o formulário abaixo para criar o primeiro.
        </p>
      ) : (
        <div className="mb-6 overflow-auto rounded-xl ring-1 ring-slate-800">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="bg-slate-950/80 text-xs uppercase text-slate-500">
              <tr className="border-b border-slate-800">
                <th className="px-4 py-3 font-medium">Nome</th>
                <th className="px-4 py-3 font-medium">Conteúdo</th>
                <th className="px-4 py-3 font-medium">Disciplina</th>
                <th className="px-4 py-3 font-medium">Flags</th>
                <th className="px-4 py-3 font-medium">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {presets.map((preset) => (
                <tr key={preset.id} className="hover:bg-slate-800/30">
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-200">{preset.label}</p>
                    <p className="text-xs text-slate-600">{preset.id}</p>
                  </td>
                  <td className="px-4 py-3 text-slate-400">
                    {contentTypeLabel(options, preset.content_type)}
                  </td>
                  <td className="px-4 py-3 text-slate-400">{preset.discipline}</td>
                  <td className="px-4 py-3 text-xs text-slate-500">
                    {preset.register_price_base && (
                      <span className="mr-1 rounded bg-emerald-600/20 px-1.5 py-0.5 text-emerald-300">
                        preço
                      </span>
                    )}
                    {preset.register_budget_model && (
                      <span className="rounded bg-violet-600/20 px-1.5 py-0.5 text-violet-300">WBS</span>
                    )}
                    {!preset.register_price_base && !preset.register_budget_model && "—"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1">
                      <button
                        type="button"
                        onClick={() => startEdit(preset)}
                        className="rounded bg-slate-700/60 px-2 py-1 text-xs text-slate-300 hover:bg-slate-700"
                      >
                        Editar
                      </button>
                      <button
                        type="button"
                        disabled={deletingId === preset.id}
                        onClick={() => handleDelete(preset)}
                        className="rounded bg-red-600/15 px-2 py-1 text-xs text-red-300 hover:bg-red-600/25 disabled:opacity-50"
                      >
                        {deletingId === preset.id ? "…" : "Excluir"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="rounded-xl bg-slate-950/50 p-4 ring-1 ring-slate-800">
        <h3 className="text-sm font-medium text-slate-300">
          {editingId ? "Editar tipo" : "Novo tipo de documento"}
        </h3>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="block sm:col-span-2">
            <span className="mb-1.5 block text-xs font-medium text-slate-400">Nome *</span>
            <input
              type="text"
              value={form.label}
              onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))}
              placeholder="Ex: Instruções Técnicas PCI / CBMAM (Incêndio)"
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-cyan-500 focus:outline-none"
            />
          </label>
          {!editingId && (
            <label className="block sm:col-span-2">
              <span className="mb-1.5 block text-xs font-medium text-slate-400">
                ID (opcional)
              </span>
              <input
                type="text"
                value={form.id}
                onChange={(e) => setForm((f) => ({ ...f, id: e.target.value }))}
                placeholder="Gerado automaticamente a partir do nome"
                className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white focus:border-cyan-500 focus:outline-none"
              />
            </label>
          )}
          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-slate-400">Tipo de conteúdo *</span>
            <select
              value={form.content_type}
              onChange={(e) => setForm((f) => ({ ...f, content_type: e.target.value }))}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none"
            >
              {options.content_types.map((ct) => (
                <option key={ct.value} value={ct.value}>
                  {ct.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-slate-400">Disciplina *</span>
            <select
              value={form.discipline}
              onChange={(e) => setForm((f) => ({ ...f, discipline: e.target.value }))}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 focus:border-cyan-500 focus:outline-none"
            >
              {options.disciplines.map((d) => (
                <option key={d.value} value={d.value}>
                  {d.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={form.register_price_base}
              onChange={(e) => setForm((f) => ({ ...f, register_price_base: e.target.checked }))}
              className="rounded border-slate-600 bg-slate-900 text-cyan-500"
            />
            <span className="text-xs text-slate-400">Registrar como base de preços (SINAPI/TCPO)</span>
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={form.register_budget_model}
              onChange={(e) => setForm((f) => ({ ...f, register_budget_model: e.target.checked }))}
              className="rounded border-slate-600 bg-slate-900 text-violet-500"
            />
            <span className="text-xs text-slate-400">Registrar como modelo de orçamento (PPD/WBS)</span>
          </label>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={saving || !form.label.trim()}
            onClick={handleSubmit}
            className={cn(
              "rounded-lg px-4 py-2 text-sm font-medium text-white disabled:opacity-50",
              editingId
                ? "bg-cyan-600/80 hover:bg-cyan-600"
                : "bg-gradient-to-r from-cyan-600 to-blue-600"
            )}
          >
            {saving ? "Salvando…" : editingId ? "Salvar alterações" : "Cadastrar tipo"}
          </button>
          {editingId && (
            <button
              type="button"
              disabled={saving}
              onClick={resetForm}
              className="rounded-lg px-4 py-2 text-sm text-slate-400 hover:text-white disabled:opacity-50"
            >
              Cancelar edição
            </button>
          )}
        </div>
      </div>

      {error && (
        <p className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-300 ring-1 ring-red-500/20">
          {error}
        </p>
      )}
      {success && (
        <p className="mt-3 rounded-lg bg-emerald-500/10 px-3 py-2 text-sm text-emerald-300 ring-1 ring-emerald-500/20">
          {success}
        </p>
      )}
      <ActionDialogHost />
    </section>
  );
}
