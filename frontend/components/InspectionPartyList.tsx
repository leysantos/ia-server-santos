"use client";

import { useMemo, useState } from "react";
import { api } from "@/services/api";
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
  art_asset_id: "",
  art_protocolo: "",
  art_url: "",
  signature_asset_id: "",
};

type Mode = "closed" | "create" | "edit" | "confirm-delete" | "confirm-edit";

export default function InspectionPartyList({
  title,
  hint,
  items,
  onChange,
  disabled,
  showArt = false,
  reportId,
}: {
  title: string;
  hint?: string;
  items: InspectionReportParty[];
  onChange: (next: InspectionReportParty[]) => void;
  disabled?: boolean;
  /** Exibe campo Nº ART (responsáveis técnicos). */
  showArt?: boolean;
  /** Quando informado, permite upload ART PDF e imagem de firma (L18/L19). */
  reportId?: string;
}) {
  const [mode, setMode] = useState<Mode>("closed");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [uploading, setUploading] = useState<"art" | "signature" | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [lookingUp, setLookingUp] = useState(false);
  const [lookupNote, setLookupNote] = useState<string | null>(null);

  const editing = useMemo(
    () => items.find((p) => p.id === editingId) || null,
    [items, editingId]
  );

  const lookupArt = async () => {
    setLookingUp(true);
    setLookupNote(null);
    setUploadError(null);
    try {
      const result = await api.lookupInspectionArt({
        crea: form.crea || undefined,
        art: form.art || undefined,
        art_protocolo: form.art_protocolo || undefined,
        probe: true,
      });
      setForm((f) => ({
        ...f,
        art_url: result.art_url || f.art_url,
        art_protocolo: f.art_protocolo || result.art_protocolo || "",
        art: f.art || result.art || "",
      }));
      const live = result.live?.reachable
        ? "portal alcançável"
        : result.live
          ? "portal sem resposta (URL preenchida)"
          : "URL gerada";
      setLookupNote(
        `${live} · ${result.source}${result.sicar_url ? ` · SICAR: ${result.sicar_url}` : ""}`
      );
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : String(err));
    } finally {
      setLookingUp(false);
    }
  };

  const openCreate = () => {
    setEditingId(null);
    setForm({ ...EMPTY_FORM });
    setUploadError(null);
    setLookupNote(null);
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
      art_asset_id: party.art_asset_id || "",
      art_protocolo: party.art_protocolo || "",
      art_url: party.art_url || "",
      signature_asset_id: party.signature_asset_id || "",
    });
    setUploadError(null);
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
    setUploadError(null);
  };

  const partyPayload = (id: string): InspectionReportParty => ({
    id,
    nome: form.nome.trim(),
    profissao: form.profissao?.trim() || "",
    crea: form.crea?.trim() || "",
    art: showArt ? form.art?.trim() || "" : "",
    email: form.email?.trim() || "",
    telefone: form.telefone?.trim() || "",
    art_asset_id: showArt ? form.art_asset_id?.trim() || "" : "",
    art_protocolo: showArt ? form.art_protocolo?.trim() || "" : "",
    art_url: showArt ? form.art_url?.trim() || "" : "",
    signature_asset_id: showArt ? form.signature_asset_id?.trim() || "" : "",
  });

  const submitForm = () => {
    const nome = form.nome.trim();
    if (!nome) return;
    if (mode === "edit") {
      setMode("confirm-edit");
      return;
    }
    onChange([...items, partyPayload(newId())]);
    closeModal();
  };

  const confirmEdit = () => {
    if (!editingId) return;
    const nome = form.nome.trim();
    if (!nome) return;
    onChange(items.map((p) => (p.id === editingId ? partyPayload(editingId) : p)));
    closeModal();
  };

  const confirmDelete = () => {
    if (!pendingDeleteId) return;
    onChange(items.filter((p) => p.id !== pendingDeleteId));
    closeModal();
  };

  const uploadForParty = async (kind: "art" | "signature", file: File | null) => {
    if (!reportId || !file || !editingId) return;
    setUploading(kind);
    setUploadError(null);
    try {
      const asset = await api.uploadInspectionReportAsset(reportId, file, { kind });
      if (kind === "art") {
        setForm((f) => ({ ...f, art_asset_id: asset.id }));
      } else {
        setForm((f) => ({ ...f, signature_asset_id: asset.id }));
        await api.saveInspectionSignatureEvidence(reportId, {
          rt_signature_asset_ids: { [editingId]: asset.id },
        });
      }
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : String(err));
    } finally {
      setUploading(null);
    }
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
                      showArt && party.art_asset_id ? "PDF ART" : "",
                      showArt && party.signature_asset_id ? "firma" : "",
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
        <div className="fixed inset-0 z-[60] flex items-center justify-center overflow-y-auto bg-slate-950/70 p-4 backdrop-blur-sm">
          <div
            role="dialog"
            aria-modal="true"
            className="my-4 w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 p-5 shadow-2xl ring-1 ring-slate-700/80"
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
                    value={(form[key] as string) || ""}
                    onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                    required={required}
                  />
                </label>
              ))}

              {showArt && (
                <>
                  <label className="block text-sm">
                    <span className="text-slate-400">Protocolo ART (L18)</span>
                    <input
                      className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
                      value={form.art_protocolo || ""}
                      onChange={(e) => setForm((f) => ({ ...f, art_protocolo: e.target.value }))}
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="text-slate-400">URL consulta ART / CREA (opcional)</span>
                    <input
                      className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
                      value={form.art_url || ""}
                      onChange={(e) => setForm((f) => ({ ...f, art_url: e.target.value }))}
                      placeholder="https://…"
                    />
                  </label>
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      disabled={disabled || lookingUp || (!form.crea && !form.art && !form.art_protocolo)}
                      onClick={lookupArt}
                      className="rounded-lg bg-slate-700 px-3 py-1.5 text-xs text-white hover:bg-slate-600 disabled:opacity-50"
                    >
                      {lookingUp ? "Consultando…" : "Consultar ART / SICAR"}
                    </button>
                    {form.art_url ? (
                      <a
                        href={form.art_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-cyan-400 hover:underline"
                      >
                        Abrir portal
                      </a>
                    ) : null}
                  </div>
                  {lookupNote ? <p className="text-[11px] text-slate-400">{lookupNote}</p> : null}
                  {reportId && mode === "edit" && (
                    <>
                      <label className="block text-sm">
                        <span className="text-slate-400">
                          Anexar PDF da ART {form.art_asset_id ? "(anexado)" : ""}
                        </span>
                        <input
                          type="file"
                          accept=".pdf,application/pdf"
                          className="mt-1 block w-full text-xs text-slate-300"
                          disabled={!!uploading || disabled}
                          onChange={(e) => uploadForParty("art", e.target.files?.[0] || null)}
                        />
                      </label>
                      <label className="block text-sm">
                        <span className="text-slate-400">
                          Imagem da firma {form.signature_asset_id ? "(anexada)" : ""} (L19)
                        </span>
                        <input
                          type="file"
                          accept="image/*"
                          className="mt-1 block w-full text-xs text-slate-300"
                          disabled={!!uploading || disabled}
                          onChange={(e) =>
                            uploadForParty("signature", e.target.files?.[0] || null)
                          }
                        />
                      </label>
                      {uploading ? (
                        <p className="text-xs text-cyan-300">Enviando {uploading}…</p>
                      ) : null}
                      {uploadError ? (
                        <p className="text-xs text-rose-300">{uploadError}</p>
                      ) : null}
                    </>
                  )}
                  {showArt && mode === "create" && reportId ? (
                    <p className="text-[11px] text-slate-500">
                      Salve o responsável e altere-o para anexar PDF ART e imagem de firma.
                    </p>
                  ) : null}
                </>
              )}
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
