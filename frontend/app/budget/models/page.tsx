"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import ActionDialog from "@/components/ActionDialog";
import BudgetSkeletonEditor, {
  skeletonFormFromRecord,
  skeletonPayloadFromForm,
} from "@/components/BudgetSkeletonEditor";
import LoadingSpinner from "@/components/LoadingSpinner";
import ShellHeader from "@/components/ShellHeader";
import { api, formatApiError } from "@/services/api";
import type { BdiObraType, BudgetSkeleton } from "@/types/api";
import { cn } from "@/lib/utils";
import { budgetBtn } from "@/lib/budget-ui";

export default function BudgetModelsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [items, setItems] = useState<BudgetSkeleton[]>([]);
  const [bdiTypes, setBdiTypes] = useState<BdiObraType[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [form, setForm] = useState(() => skeletonFormFromRecord(null));
  const [dialog, setDialog] = useState<{
    open: boolean;
    title: string;
    message: string;
    variant: "success" | "error" | "confirm" | "info";
    onConfirm?: () => void;
  }>({ open: false, title: "", message: "", variant: "info" });

  const refresh = useCallback(() => {
    setLoading(true);
    return api
      .pricingListSkeletons()
      .then((r) => setItems(r.items))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refresh();
    api.pricingBdiTypes().then((r) => setBdiTypes(r.types)).catch(() => {});
  }, [refresh]);

  const selectSkeleton = (sk: BudgetSkeleton | null) => {
    if (!sk) {
      setSelectedId(null);
      setForm(skeletonFormFromRecord(null));
      return;
    }
    setSelectedId(sk.id);
    setForm(skeletonFormFromRecord(sk));
  };

  const handleNew = () => selectSkeleton(null);

  const handleSave = async () => {
    const payload = skeletonPayloadFromForm(form);
    if (!payload.name) {
      setDialog({
        open: true,
        title: "Validação",
        message: "Informe o nome do modelo de orçamento.",
        variant: "error",
      });
      return;
    }
    if (payload.etapas.length === 0) {
      setDialog({
        open: true,
        title: "Validação",
        message: "Adicione pelo menos uma etapa com nome.",
        variant: "error",
      });
      return;
    }

    setSaving(true);
    try {
      if (selectedId) {
        await api.pricingUpdateSkeleton(selectedId, payload);
      } else {
        const created = await api.pricingCreateSkeleton(payload);
        setSelectedId(created.id);
      }
      await refresh();
      setDialog({
        open: true,
        title: "Salvo",
        message: "Modelo de orçamento salvo com sucesso.",
        variant: "success",
      });
    } catch (err) {
      setDialog({
        open: true,
        title: "Erro ao salvar",
        message: formatApiError(err instanceof Error ? err.message : String(err)),
        variant: "error",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = () => {
    if (!selectedId) return;
    setDialog({
      open: true,
      title: "Excluir modelo",
      message: `Remover o esqueleto "${form.name}"? Esta ação não pode ser desfeita.`,
      variant: "confirm",
      onConfirm: async () => {
        setSaving(true);
        try {
          await api.pricingDeleteSkeleton(selectedId);
          handleNew();
          await refresh();
        } catch (err) {
          setDialog({
            open: true,
            title: "Erro",
            message: formatApiError(err instanceof Error ? err.message : String(err)),
            variant: "error",
          });
        } finally {
          setSaving(false);
        }
      },
    });
  };

  const bdiOptions = bdiTypes.map((t) => ({ code: t.code, label: t.label }));

  return (
    <>
      <ShellHeader className="px-6">
        <div className="min-w-0">
          <h1 className="truncate text-lg font-semibold gradient-text">Modelos de orçamento</h1>
          <p className="truncate text-sm text-slate-500">
            Cadastre esqueletos WBS (etapas e sub-etapas) para iniciar novos orçamentos
          </p>
        </div>
      </ShellHeader>

      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden p-4 md:flex-row md:p-6">
        <aside className="flex w-full shrink-0 flex-col md:w-72">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Cadastrados</p>
            <button
              type="button"
              onClick={handleNew}
              className="text-xs text-brand-400 hover:text-brand-300"
            >
              + Novo
            </button>
          </div>
          <div className="app-card min-h-[200px] flex-1 overflow-y-auto p-2 md:max-h-none">
            {loading ? (
              <div className="flex justify-center py-8">
                <LoadingSpinner size="sm" label="Carregando..." />
              </div>
            ) : items.length === 0 ? (
              <p className="px-2 py-6 text-center text-sm text-slate-500">Nenhum modelo cadastrado.</p>
            ) : (
              <ul className="space-y-1">
                {items.map((sk) => (
                  <li key={sk.id}>
                    <button
                      type="button"
                      onClick={() => selectSkeleton(sk)}
                      className={cn(
                        "w-full rounded-lg px-3 py-2 text-left transition-colors",
                        selectedId === sk.id
                          ? "bg-brand-500/15 text-brand-100"
                          : "text-slate-300 hover:bg-white/5"
                      )}
                    >
                      <p className="text-sm font-medium">{sk.name}</p>
                      <p className="text-[10px] text-slate-500">
                        {sk.etapas.length} etapa(s) · {sk.obra_type}
                      </p>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <Link
            href="/budget?action=new"
            className={cn(
              budgetBtn,
              "mt-3 w-full bg-brand-600/20 text-center text-sm text-brand-300 hover:bg-brand-600/30"
            )}
          >
            Criar orçamento a partir de modelo
          </Link>
        </aside>

        <section className="app-card min-h-0 flex-1 overflow-y-auto p-4 md:p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-slate-200">
              {selectedId ? "Editar modelo" : "Novo modelo de orçamento"}
            </h2>
            <div className="flex flex-wrap gap-2">
              {selectedId && (
                <button
                  type="button"
                  disabled={saving}
                  onClick={handleDelete}
                  className={cn(budgetBtn, "text-red-400 hover:bg-red-500/10")}
                >
                  Excluir
                </button>
              )}
              <button
                type="button"
                disabled={saving}
                onClick={handleSave}
                className={cn(
                  budgetBtn,
                  "bg-brand-600/20 px-4 text-brand-300 hover:bg-brand-600/30"
                )}
              >
                {saving ? "Salvando..." : "Salvar modelo"}
              </button>
            </div>
          </div>

          <BudgetSkeletonEditor
            value={form}
            bdiTypes={bdiOptions}
            disabled={saving}
            onChange={setForm}
          />
        </section>
      </div>

      <ActionDialog
        open={dialog.open}
        title={dialog.title}
        message={dialog.message}
        variant={dialog.variant}
        onCancel={() => setDialog((d) => ({ ...d, open: false }))}
        onConfirm={dialog.onConfirm}
      />
    </>
  );
}
