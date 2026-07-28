"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/services/api";
import type {
  InspectionAssayResult,
  InspectionAssayResultsView,
  InspectionAssaySuggestedTest,
} from "@/types/api";

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `ar_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

const EMPTY_FORM: Omit<InspectionAssayResult, "id" | "created_at" | "updated_at"> = {
  test_code: "",
  ensaio: "",
  local: "",
  valor: "",
  unidade: "",
  valor_nominal: "",
  data_ensaio: "",
  laboratorio: "",
  responsavel: "",
  conclusao: "",
  pathology_refs: [],
  norma_ref: "",
  status: "executado",
  observacoes: "",
};

type Mode = "closed" | "create" | "edit" | "confirm-delete" | "confirm-edit";

function suggestedToForm(s: InspectionAssaySuggestedTest): typeof EMPTY_FORM {
  return {
    test_code: s.test_code || "",
    ensaio: s.ensaio || "",
    local: "",
    valor: "",
    unidade: "",
    valor_nominal: "",
    data_ensaio: "",
    laboratorio: "",
    responsavel: "",
    conclusao: "",
    pathology_refs: [...(s.pathology_refs || [])],
    norma_ref: s.norma_ref || "",
    status: "executado",
    observacoes: "",
  };
}

function formatResultValue(item: InspectionAssayResult): string {
  const val = (item.valor || "").trim();
  const unit = (item.unidade || "").trim();
  if (!val) return "—";
  return unit ? `${val} ${unit}` : val;
}

export default function InspectionAssayResultsPanel({
  reportId,
  disabled,
  onSaved,
}: {
  reportId: string;
  disabled?: boolean;
  onSaved?: () => void;
}) {
  const [view, setView] = useState<InspectionAssayResultsView | null>(null);
  const [items, setItems] = useState<InspectionAssayResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [mode, setMode] = useState<Mode>("closed");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [pathologyInput, setPathologyInput] = useState("");

  const load = useCallback(async () => {
    if (!reportId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.getInspectionAssayResults(reportId);
      setView(data);
      setItems(data.items || []);
      setDirty(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [reportId]);

  useEffect(() => {
    load().catch(() => undefined);
  }, [load]);

  const editing = useMemo(
    () => items.find((i) => i.id === editingId) || null,
    [items, editingId]
  );

  const pendingDelete = items.find((i) => i.id === pendingDeleteId);

  const openCreate = (prefill?: InspectionAssaySuggestedTest) => {
    setEditingId(null);
    setForm(prefill ? suggestedToForm(prefill) : { ...EMPTY_FORM });
    setPathologyInput(
      prefill?.pathology_refs?.length ? prefill.pathology_refs.join(", ") : ""
    );
    setMode("create");
  };

  const openEdit = (item: InspectionAssayResult) => {
    setEditingId(item.id);
    setForm({
      test_code: item.test_code || "",
      ensaio: item.ensaio || "",
      local: item.local || "",
      valor: item.valor || "",
      unidade: item.unidade || "",
      valor_nominal: item.valor_nominal || "",
      data_ensaio: item.data_ensaio || "",
      laboratorio: item.laboratorio || "",
      responsavel: item.responsavel || "",
      conclusao: item.conclusao || "",
      pathology_refs: [...(item.pathology_refs || [])],
      norma_ref: item.norma_ref || "",
      status: item.status || "executado",
      observacoes: item.observacoes || "",
    });
    setPathologyInput((item.pathology_refs || []).join(", "));
    setMode("edit");
  };

  const closeModal = () => {
    setMode("closed");
    setEditingId(null);
    setPendingDeleteId(null);
    setForm({ ...EMPTY_FORM });
    setPathologyInput("");
  };

  const parsePathologyRefs = (raw: string): string[] => {
    return raw
      .split(/[,;\s]+/)
      .map((p) => p.trim().toUpperCase())
      .filter(Boolean);
  };

  const buildItemFromForm = (id: string, existing?: InspectionAssayResult): InspectionAssayResult => {
    const now = new Date().toISOString().slice(0, 19);
    return {
      id,
      test_code: form.test_code.trim(),
      ensaio: form.ensaio.trim(),
      local: form.local.trim(),
      valor: form.valor.trim(),
      unidade: form.unidade.trim(),
      valor_nominal: form.valor_nominal?.trim() || null,
      data_ensaio: form.data_ensaio?.trim() || null,
      laboratorio: form.laboratorio?.trim() || null,
      responsavel: form.responsavel?.trim() || null,
      conclusao: form.conclusao?.trim() || null,
      pathology_refs: parsePathologyRefs(pathologyInput),
      norma_ref: form.norma_ref?.trim() || null,
      status: form.status,
      observacoes: form.observacoes?.trim() || null,
      created_at: existing?.created_at || now,
      updated_at: now,
    };
  };

  const submitForm = () => {
    const ensaio = form.ensaio.trim();
    const code = form.test_code.trim();
    if (!ensaio && !code) return;
    if (form.status === "executado" && !form.valor.trim()) return;
    if (mode === "edit") {
      setMode("confirm-edit");
      return;
    }
    const next = [
      ...items,
      buildItemFromForm(newId()),
    ];
    setItems(next);
    setDirty(true);
    closeModal();
  };

  const confirmEdit = () => {
    if (!editingId) return;
    const next = items.map((i) =>
      i.id === editingId ? buildItemFromForm(editingId, i) : i
    );
    setItems(next);
    setDirty(true);
    closeModal();
  };

  const requestDelete = (id: string) => {
    setPendingDeleteId(id);
    setMode("confirm-delete");
  };

  const confirmDelete = () => {
    if (!pendingDeleteId) return;
    setItems(items.filter((i) => i.id !== pendingDeleteId));
    setDirty(true);
    closeModal();
  };

  const saveAll = async () => {
    setSaving(true);
    setError(null);
    try {
      const data = await api.saveInspectionAssayResults(reportId, items);
      setView(data);
      setItems(data.items || []);
      setDirty(false);
      onSaved?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const suggested = view?.suggested_tests || [];
  const pathologies = view?.pathologies || [];

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-white">Resultados de ensaios (L16)</h3>
          <p className="mt-0.5 text-xs text-slate-500">
            Valores medidos após campanha de laboratório ou campo — entram na tabela do Word/PDF.
          </p>
          {view ? (
            <p className="mt-1 text-xs text-slate-400">
              {view.count_executed} executado(s) · {view.count_total} registro(s)
            </p>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-wrap gap-1">
          <button
            type="button"
            disabled={disabled || loading}
            onClick={() => openCreate()}
            className="rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-500 disabled:opacity-50"
          >
            Incluir
          </button>
          <button
            type="button"
            disabled={disabled || loading || saving || !dirty}
            onClick={saveAll}
            className="rounded-lg bg-cyan-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-cyan-600 disabled:opacity-50"
          >
            {saving ? "Salvando…" : "Salvar resultados"}
          </button>
        </div>
      </div>

      {error ? (
        <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-200">{error}</p>
      ) : null}

      {suggested.length > 0 && (
        <div className="rounded-xl border border-slate-700/80 bg-slate-950/50 p-3">
          <p className="text-xs font-medium text-slate-400">Ensaios sugeridos no laudo</p>
          <ul className="mt-2 space-y-1">
            {suggested.map((s, idx) => (
              <li key={`${s.test_code}-${idx}`} className="flex items-center justify-between gap-2 text-xs">
                <span className="min-w-0 truncate text-slate-300">
                  {s.test_code ? `[${s.test_code}] ` : ""}
                  {s.ensaio}
                  {s.pathology_refs?.length ? ` · ${s.pathology_refs.join(", ")}` : ""}
                </span>
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => openCreate(s)}
                  className="shrink-0 rounded-md bg-slate-700 px-2 py-0.5 text-[11px] text-white hover:bg-slate-600 disabled:opacity-50"
                >
                  Preencher
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="max-h-56 overflow-y-auto rounded-xl border border-slate-700 bg-slate-950/60">
        {loading && items.length === 0 ? (
          <p className="px-3 py-4 text-center text-xs text-slate-500">Carregando…</p>
        ) : items.length === 0 ? (
          <p className="px-3 py-4 text-center text-xs text-slate-500">
            Nenhum resultado cadastrado. Use &quot;Incluir&quot; ou preencha a partir dos ensaios sugeridos.
          </p>
        ) : (
          <ul className="divide-y divide-slate-800">
            {items.map((item) => (
              <li
                key={item.id}
                className="flex items-start justify-between gap-2 px-3 py-2.5"
              >
                <div className="min-w-0 text-sm">
                  <p className="truncate font-medium text-slate-100">
                    {item.test_code ? `[${item.test_code}] ` : ""}
                    {item.ensaio || "—"}
                  </p>
                  <p className="truncate text-xs text-slate-400">
                    {[
                      item.status !== "executado" ? item.status : formatResultValue(item),
                      item.local,
                      item.data_ensaio,
                      (item.pathology_refs || []).join(", "),
                    ]
                      .filter(Boolean)
                      .join(" · ") || "—"}
                  </p>
                  {item.conclusao ? (
                    <p className="mt-0.5 line-clamp-2 text-xs text-slate-500">{item.conclusao}</p>
                  ) : null}
                </div>
                <div className="flex shrink-0 gap-1">
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => openEdit(item)}
                    className="rounded-md bg-slate-700 px-2 py-1 text-[11px] text-white hover:bg-slate-600 disabled:opacity-50"
                  >
                    Alterar
                  </button>
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => requestDelete(item.id)}
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

      {pathologies.length > 0 && (
        <p className="text-[11px] text-slate-500">
          Patologias no laudo: {pathologies.map((p) => p.code).filter((c) => c !== "—").join(", ") || "—"}
        </p>
      )}

      {(mode === "create" || mode === "edit") && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center overflow-y-auto bg-slate-950/70 p-4 backdrop-blur-sm">
          <div
            role="dialog"
            aria-modal="true"
            className="my-4 w-full max-w-lg rounded-2xl border border-slate-700 bg-slate-900 p-5 shadow-2xl ring-1 ring-slate-700/80"
          >
            <h4 className="text-base font-semibold text-white">
              {mode === "create" ? "Incluir resultado de ensaio" : "Alterar resultado"}
            </h4>
            <p className="mt-1 text-xs text-slate-400">
              {mode === "edit" && editing
                ? `Editando: ${editing.ensaio || editing.test_code}`
                : "Registre o valor medido após execução em laboratório ou campo."}
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="block text-sm sm:col-span-1">
                <span className="text-slate-400">Código do ensaio</span>
                <input
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
                  value={form.test_code}
                  onChange={(e) => setForm((f) => ({ ...f, test_code: e.target.value }))}
                />
              </label>
              <label className="block text-sm sm:col-span-1">
                <span className="text-slate-400">Nome do ensaio *</span>
                <input
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
                  value={form.ensaio}
                  onChange={(e) => setForm((f) => ({ ...f, ensaio: e.target.value }))}
                />
              </label>
              <label className="block text-sm sm:col-span-2">
                <span className="text-slate-400">Local / elemento</span>
                <input
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
                  value={form.local}
                  onChange={(e) => setForm((f) => ({ ...f, local: e.target.value }))}
                />
              </label>
              <label className="block text-sm">
                <span className="text-slate-400">Valor medido *</span>
                <input
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
                  value={form.valor}
                  onChange={(e) => setForm((f) => ({ ...f, valor: e.target.value }))}
                  placeholder="ex.: 28,5"
                />
              </label>
              <label className="block text-sm">
                <span className="text-slate-400">Unidade</span>
                <input
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
                  value={form.unidade}
                  onChange={(e) => setForm((f) => ({ ...f, unidade: e.target.value }))}
                  placeholder="MPa, mm, %…"
                />
              </label>
              <label className="block text-sm">
                <span className="text-slate-400">Valor nominal / referência</span>
                <input
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
                  value={form.valor_nominal || ""}
                  onChange={(e) => setForm((f) => ({ ...f, valor_nominal: e.target.value }))}
                />
              </label>
              <label className="block text-sm">
                <span className="text-slate-400">Data do ensaio</span>
                <input
                  type="date"
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
                  value={form.data_ensaio || ""}
                  onChange={(e) => setForm((f) => ({ ...f, data_ensaio: e.target.value }))}
                />
              </label>
              <label className="block text-sm">
                <span className="text-slate-400">Status</span>
                <select
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
                  value={form.status}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      status: e.target.value as InspectionAssayResult["status"],
                    }))
                  }
                >
                  <option value="executado">Executado</option>
                  <option value="pendente">Pendente</option>
                  <option value="cancelado">Cancelado</option>
                </select>
              </label>
              <label className="block text-sm sm:col-span-1">
                <span className="text-slate-400">Laboratório</span>
                <input
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
                  value={form.laboratorio || ""}
                  onChange={(e) => setForm((f) => ({ ...f, laboratorio: e.target.value }))}
                />
              </label>
              <label className="block text-sm sm:col-span-1">
                <span className="text-slate-400">Responsável técnico</span>
                <input
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
                  value={form.responsavel || ""}
                  onChange={(e) => setForm((f) => ({ ...f, responsavel: e.target.value }))}
                />
              </label>
              <label className="block text-sm sm:col-span-2">
                <span className="text-slate-400">Patologias vinculadas (P1, P2…)</span>
                <input
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
                  value={pathologyInput}
                  onChange={(e) => setPathologyInput(e.target.value)}
                  placeholder="P1, P3"
                />
              </label>
              <label className="block text-sm sm:col-span-2">
                <span className="text-slate-400">Norma de referência</span>
                <input
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
                  value={form.norma_ref || ""}
                  onChange={(e) => setForm((f) => ({ ...f, norma_ref: e.target.value }))}
                />
              </label>
              <label className="block text-sm sm:col-span-2">
                <span className="text-slate-400">Conclusão</span>
                <textarea
                  className="mt-1 min-h-16 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
                  value={form.conclusao || ""}
                  onChange={(e) => setForm((f) => ({ ...f, conclusao: e.target.value }))}
                />
              </label>
              <label className="block text-sm sm:col-span-2">
                <span className="text-slate-400">Observações</span>
                <textarea
                  className="mt-1 min-h-12 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
                  value={form.observacoes || ""}
                  onChange={(e) => setForm((f) => ({ ...f, observacoes: e.target.value }))}
                />
              </label>
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
                disabled={
                  (!form.ensaio.trim() && !form.test_code.trim()) ||
                  (form.status === "executado" && !form.valor.trim())
                }
                onClick={submitForm}
                className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-500 disabled:opacity-50"
              >
                {mode === "create" ? "Adicionar à lista" : "Salvar alterações"}
              </button>
            </div>
          </div>
        </div>
      )}

      {mode === "confirm-edit" && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-2xl border border-amber-500/30 bg-slate-900 p-5 shadow-2xl ring-1 ring-amber-500/20">
            <h4 className="text-base font-semibold text-amber-100">Confirmar alteração?</h4>
            <p className="mt-2 text-sm text-slate-300">
              Confirma a atualização de{" "}
              <strong className="text-white">{editing?.ensaio || "este resultado"}</strong>?
              Clique em &quot;Salvar resultados&quot; para persistir no laudo.
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
                Confirmar
              </button>
            </div>
          </div>
        </div>
      )}

      {mode === "confirm-delete" && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-2xl border border-rose-500/40 bg-slate-900 p-5 shadow-2xl ring-1 ring-rose-500/25">
            <h4 className="text-base font-semibold text-rose-100">Excluir resultado?</h4>
            <p className="mt-2 text-sm text-slate-300">
              Remover{" "}
              <strong className="text-white">{pendingDelete?.ensaio || "este registro"}</strong>?
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
