"use client";

import { useMemo, useState } from "react";
import type { InspectionReportParty } from "@/types/api";

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `p_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

const EMPTY_FORM: Omit<InspectionReportParty, "id"> = {
  nome: "",
  profissao: "",
  crea: "",
  art: "",
  email: "",
  telefone: "",
};

type Mode = "closed" | "create" | "edit" | "confirm-delete" | "confirm-edit";

export default function InspectionPartyList({
  title,
  hint,
  items,
  onChange,
  disabled,
  showArt = false,
}: {
  title: string;
  hint?: string;
  items: InspectionReportParty[];
  onChange: (next: InspectionReportParty[]) => void;
  disabled?: boolean;
  /** Exibe campo Nº ART (responsáveis técnicos). */
  showArt?: boolean;
}) {
  const [mode, setMode] = useState<Mode>("closed");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  const editing = useMemo(
    () => items.find((p) => p.id === editingId) || null,
    [items, editingId]
  );

  const openCreate = () => {
    setEditingId(null);
    setForm({ ...EMPTY_FORM });
    setMode("create");
  };

  const openEdit = (party: InspectionReportParty) => {
    setEditingId(party.id);
    setForm({
      nome: party.nome || "",
      profissao: party.profissao || "",
      crea: party.crea || "",
      art: party.art || "",
      email: party.email || "",
      telefone: party.telefone || "",
    });
    setMode("edit");
  };

  const requestDelete = (id: string) => {
    setPendingDeleteId(id);
    setMode("confirm-delete");
  };

  const closeModal = () => {
    setMode("closed");
    setEditingId(null);
    setPendingDeleteId(null);
    setForm({ ...EMPTY_FORM });
  };

  const submitForm = () => {
    const nome = form.nome.trim();
    if (!nome) return;
    if (mode === "edit") {
      setMode("confirm-edit");
      return;
    }
    onChange([
      ...items,
      {
        id: newId(),
        nome,
        profissao: form.profissao?.trim() || "",
        crea: form.crea?.trim() || "",
        art: showArt ? form.art?.trim() || "" : "",
        email: form.email?.trim() || "",
        telefone: form.telefone?.trim() || "",
      },
    ]);
    closeModal();
  };

  const confirmEdit = () => {
    if (!editingId) return;
    const nome = form.nome.trim();
    if (!nome) return;
    onChange(
      items.map((p) =>
        p.id === editingId
          ? {
              ...p,
              nome,
              profissao: form.profissao?.trim() || "",
              crea: form.crea?.trim() || "",
              art: showArt ? form.art?.trim() || "" : p.art || "",
              email: form.email?.trim() || "",
              telefone: form.telefone?.trim() || "",
            }
          : p
      )
    );
    closeModal();
  };

  const confirmDelete = () => {
    if (!pendingDeleteId) return;
    onChange(items.filter((p) => p.id !== pendingDeleteId));
    closeModal();
  };

  const pendingDelete = items.find((p) => p.id === pendingDeleteId);

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-white">{title}</h3>
          {hint ? <p className="mt-0.5 text-xs text-slate-500">{hint}</p> : null}
        </div>
        <button
          type="button"
          disabled={disabled}
          onClick={openCreate}
          className="shrink-0 rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-500 disabled:opacity-50"
        >
          Incluir
        </button>
      </div>

      <div className="max-h-48 overflow-y-auto rounded-xl border border-slate-700 bg-slate-950/60">
        {items.length === 0 ? (
          <p className="px-3 py-4 text-center text-xs text-slate-500">
            Nenhum responsável na lista.
          </p>
        ) : (
          <ul className="divide-y divide-slate-800">
            {items.map((party) => (
              <li
                key={party.id}
                className="flex items-start justify-between gap-2 px-3 py-2.5"
              >
                <div className="min-w-0 text-sm">
                  <p className="truncate font-medium text-slate-100">{party.nome}</p>
                  <p className="truncate text-xs text-slate-400">
                    {[
                      party.profissao,
                      party.crea ? `CREA ${party.crea}` : "",
                      showArt && party.art ? `ART ${party.art}` : "",
                    ]
                      .filter(Boolean)
                      .join(" · ") || "—"}
                  </p>
                </div>
                <div className="flex shrink-0 gap-1">
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => openEdit(party)}
                    className="rounded-md bg-slate-700 px-2 py-1 text-[11px] text-white hover:bg-slate-600 disabled:opacity-50"
                  >
                    Alterar
                  </button>
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => requestDelete(party.id)}
                    className="rounded-md bg-rose-800/70 px-2 py-1 text-[11px] text-rose-100 hover:bg-rose-700 disabled:opacity-50"
                  >
                    Excluir
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {(mode === "create" || mode === "edit") && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm">
          <div
            role="dialog"
            aria-modal="true"
            className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 p-5 shadow-2xl ring-1 ring-slate-700/80"
          >
            <h4 className="text-base font-semibold text-white">
              {mode === "create" ? "Incluir responsável" : "Alterar responsável"}
            </h4>
            <p className="mt-1 text-xs text-slate-400">
              {mode === "edit" && editing
                ? `Editando: ${editing.nome}`
                : "Preencha os dados profissionais."}
            </p>
            <div className="mt-4 grid gap-3">
              {(
                [
                  ["nome", "Nome completo", true],
                  ["profissao", "Profissão / especialidade", false],
                  ["crea", "Nº CREA / registro", false],
                  ...(showArt ? ([["art", "Nº ART", false]] as const) : []),
                  ["telefone", "Telefone", false],
                  ["email", "E-mail", false],
                ] as const
              ).map(([key, label, required]) => (
                <label key={key} className="block text-sm">
                  <span className="text-slate-400">
                    {label}
                    {required ? " *" : ""}
                  </span>
                  <input
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
                    value={form[key] || ""}
                    onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                    required={required}
                  />
                </label>
              ))}
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={closeModal}
                className="rounded-lg bg-slate-700 px-4 py-2 text-sm text-white"
              >
                Cancelar
              </button>
              <button
                type="button"
                disabled={!form.nome.trim()}
                onClick={submitForm}
                className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-500 disabled:opacity-50"
              >
                {mode === "create" ? "Adicionar" : "Salvar alterações"}
              </button>
            </div>
          </div>
        </div>
      )}

      {mode === "confirm-edit" && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-sm">
          <div
            role="alertdialog"
            aria-modal="true"
            className="w-full max-w-sm rounded-2xl border border-amber-500/30 bg-slate-900 p-5 shadow-2xl ring-1 ring-amber-500/20"
          >
            <h4 className="text-base font-semibold text-amber-100">Confirmar alteração?</h4>
            <p className="mt-2 text-sm text-slate-300">
              Confirma a atualização dos dados de{" "}
              <strong className="text-white">{editing?.nome || "este responsável"}</strong>?
              As mudanças serão usadas no Word/PDF na próxima exportação.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setMode("edit")}
                className="rounded-lg bg-slate-700 px-4 py-2 text-sm text-white"
              >
                Voltar
              </button>
              <button
                type="button"
                onClick={confirmEdit}
                className="rounded-lg bg-cyan-600 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-500"
              >
                Confirmar alteração
              </button>
            </div>
          </div>
        </div>
      )}

      {mode === "confirm-delete" && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-sm">
          <div
            role="alertdialog"
            aria-modal="true"
            className="w-full max-w-sm rounded-2xl border border-rose-500/40 bg-slate-900 p-5 shadow-2xl ring-1 ring-rose-500/25"
          >
            <h4 className="text-base font-semibold text-rose-100">Excluir responsável?</h4>
            <p className="mt-2 text-sm text-slate-300">
              Remover{" "}
              <strong className="text-white">{pendingDelete?.nome || "este responsável"}</strong>{" "}
              da lista? Esta ação não pode ser desfeita automaticamente.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={closeModal}
                className="rounded-lg bg-slate-700 px-4 py-2 text-sm text-white"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={confirmDelete}
                className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white hover:bg-rose-500"
              >
                Excluir
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
