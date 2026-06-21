"use client";

import { useCallback, useRef, useState } from "react";
import ActionDialog from "@/components/ActionDialog";
import { useNormBulkImport } from "@/context/NormBulkImportContext";
import { cn } from "@/lib/utils";
import {
  collectPdfsFromDataTransfer,
  pickFolderPdfs,
  supportsDirectoryPicker,
} from "@/lib/normFolderPicker";
import { downloadTextFile } from "@/services/api";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTotalSize(files: File[]): string {
  const total = files.reduce((sum, f) => sum + f.size, 0);
  return formatBytes(total);
}

type PendingSelection = {
  files: File[];
  folderName: string | null;
};

const CONFIRM_FILE_THRESHOLD = 5;

export default function NormBulkImport() {
  const filesInputRef = useRef<HTMLInputElement>(null);
  const {
    selectedFiles: pdfFiles,
    setSelectedFiles,
    clearSelectedFiles,
    importing,
    progress,
    resultSummary,
    errors,
    error: jobError,
    lastReport,
    startImport,
    clearResult,
  } = useNormBulkImport();

  const [dragOver, setDragOver] = useState(false);
  const [scanningFolder, setScanningFolder] = useState(false);
  const [forceOverwrite, setForceOverwrite] = useState(false);
  const [useAiFallback, setUseAiFallback] = useState(false);
  const [markOutdated, setMarkOutdated] = useState(true);
  const [selectionError, setSelectionError] = useState<string | null>(null);
  const [selectedFolderName, setSelectedFolderName] = useState<string | null>(null);
  const [confirmDialog, setConfirmDialog] = useState<{
    open: boolean;
    pending: PendingSelection | null;
  }>({ open: false, pending: null });

  const folderPickerAvailable = supportsDirectoryPicker();
  const displayError = selectionError ?? jobError;

  const resetFilesInput = useCallback(() => {
    if (filesInputRef.current) filesInputRef.current.value = "";
  }, []);

  const pickPdfs = useCallback(
    (incoming: File[], folderName: string | null = null) => {
      if (!incoming.length) {
        setSelectionError("Selecione ao menos um arquivo PDF.");
        return;
      }
      setSelectedFiles(incoming);
      setSelectedFolderName(folderName);
      setSelectionError(null);
      clearResult();
    },
    [setSelectedFiles, clearResult]
  );

  const openConfirmOrApply = useCallback(
    (pdfs: File[], folderName: string | null) => {
      if (!pdfs.length) {
        setSelectionError(
          folderName
            ? `Nenhum PDF encontrado na pasta «${folderName}».`
            : "Nenhum PDF encontrado na seleção."
        );
        return;
      }

      if (folderName || pdfs.length >= CONFIRM_FILE_THRESHOLD) {
        setConfirmDialog({
          open: true,
          pending: { files: pdfs, folderName },
        });
        return;
      }

      pickPdfs(pdfs, folderName);
    },
    [pickPdfs]
  );

  const requestPdfSelection = useCallback(
    (incoming: FileList | File[]) => {
      const pdfs = Array.from(incoming).filter((f) => f.name.toLowerCase().endsWith(".pdf"));
      openConfirmOrApply(pdfs, null);
      resetFilesInput();
    },
    [openConfirmOrApply, resetFilesInput]
  );

  const handleSelectFolder = useCallback(async () => {
    if (!folderPickerAvailable) {
      setSelectionError(
        "Seu navegador não suporta seleção de pasta sem popup nativo. " +
          "Use Chrome ou Edge, arraste a pasta para a área tracejada, ou o script CLI " +
          "(backend/scripts/ingest_nbr_folder.py)."
      );
      return;
    }

    setSelectionError(null);
    setScanningFolder(true);
    try {
      const { files, folderName } = await pickFolderPdfs();
      openConfirmOrApply(files, folderName);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      setSelectionError(err instanceof Error ? err.message : "Falha ao ler a pasta");
    } finally {
      setScanningFolder(false);
    }
  }, [folderPickerAvailable, openConfirmOrApply]);

  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      if (!e.dataTransfer) return;

      setSelectionError(null);
      setScanningFolder(true);
      try {
        const { files, folderName } = await collectPdfsFromDataTransfer(e.dataTransfer);
        openConfirmOrApply(files, folderName);
      } catch (err) {
        setSelectionError(err instanceof Error ? err.message : "Falha ao ler arquivos soltos");
      } finally {
        setScanningFolder(false);
      }
    },
    [openConfirmOrApply]
  );

  const handleConfirmSelection = useCallback(() => {
    const pending = confirmDialog.pending;
    if (!pending) return;
    pickPdfs(pending.files, pending.folderName);
    setConfirmDialog({ open: false, pending: null });
    resetFilesInput();
  }, [confirmDialog.pending, pickPdfs, resetFilesInput]);

  const handleCancelSelection = useCallback(() => {
    setConfirmDialog({ open: false, pending: null });
    resetFilesInput();
  }, [resetFilesInput]);

  const confirmTitle = confirmDialog.pending
    ? `Carregar ${confirmDialog.pending.files.length.toLocaleString("pt-BR")} arquivo(s) para a biblioteca?`
    : "";

  const confirmMessage = confirmDialog.pending
    ? (() => {
        const { files, folderName } = confirmDialog.pending!;
        const totalSize = formatTotalSize(files);
        const countLabel = `${files.length.toLocaleString("pt-BR")} PDF(s) · ${totalSize}`;
        if (folderName) {
          return (
            `Isso importará todos os PDFs da pasta «${folderName}» (${countLabel}).\n\n` +
            "Os arquivos serão enviados ao IA Server Santos para classificação automática e indexação na base de conhecimento.\n\n" +
            "Faça isso somente se você confiar neste ambiente.\n\n" +
            "Você pode navegar para outras páginas — a importação continua em background."
          );
        }
        return (
          `Isso adicionará ${countLabel} à fila de importação.\n\n` +
          "Os arquivos serão enviados ao IA Server Santos para classificação automática e indexação.\n\n" +
          "Faça isso somente se você confiar neste ambiente.\n\n" +
          "Você pode navegar para outras páginas — a importação continua em background."
        );
      })()
    : "";

  const handleImport = () => {
    if (!pdfFiles.length || importing) return;
    setSelectionError(null);
    startImport({
      files: pdfFiles,
      folderName: selectedFolderName,
      options: {
        force: forceOverwrite,
        use_ai_fallback: useAiFallback,
        mark_edition_outdated: markOutdated,
      },
    });
  };

  const handleClear = () => {
    if (importing) return;
    clearSelectedFiles();
    setSelectedFolderName(null);
    dismissResult();
    setSelectionError(null);
    resetFilesInput();
  };

  const busy = importing || scanningFolder;
  const showProgress = importing || (progress && progress.phase === "complete" && resultSummary);

  return (
    <section className="rounded-2xl bg-slate-900/40 p-6 ring-1 ring-slate-800">
      <h2 className="mb-1 text-base font-semibold text-white">Importação em lote — NBRs e NRs</h2>
      <p className="mb-4 text-sm text-slate-500">
        Selecione uma pasta ou vários PDFs de normas. A importação continua em background se você
        navegar para o Console ou outras páginas — acompanhe pelo banner no topo ou pelo painel de
        atividades.
      </p>

      {importing && (
        <p className="mb-4 rounded-lg border border-violet-500/30 bg-violet-950/30 px-4 py-2 text-xs text-violet-200">
          Importação em andamento — pode sair desta página sem interromper o processo.
        </p>
      )}

      <div className="mb-4 grid gap-3 sm:grid-cols-2">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={markOutdated}
            onChange={(e) => setMarkOutdated(e.target.checked)}
            disabled={importing}
            className="rounded border-slate-600 bg-slate-900 text-cyan-500"
          />
          <span className="text-xs text-slate-400">
            Marcar como acervo histórico (edição possivelmente desatualizada)
          </span>
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={useAiFallback}
            onChange={(e) => setUseAiFallback(e.target.checked)}
            disabled={importing}
            className="rounded border-slate-600 bg-slate-900 text-violet-500"
          />
          <span className="text-xs text-slate-400">
            Usar IA leve só em arquivos sem código no nome (~5% do lote)
          </span>
        </label>
        <label className="flex items-center gap-2 sm:col-span-2">
          <input
            type="checkbox"
            checked={forceOverwrite}
            onChange={(e) => setForceOverwrite(e.target.checked)}
            disabled={importing}
            className="rounded border-slate-600 bg-slate-900 text-amber-500"
          />
          <span className="text-xs text-slate-400">
            Substituir PDFs já existentes com o mesmo nome
          </span>
        </label>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={cn(
          "rounded-xl border-2 border-dashed p-6 text-center transition",
          dragOver
            ? "border-violet-400 bg-violet-500/10"
            : "border-slate-700 bg-slate-950/40 hover:border-slate-500",
          scanningFolder && "pointer-events-none opacity-60"
        )}
      >
        {scanningFolder ? (
          <div>
            <p className="text-sm text-violet-300">Lendo pasta e filtrando PDFs…</p>
            <p className="mt-1 text-xs text-slate-500">Aguarde — acervos grandes podem levar alguns segundos</p>
          </div>
        ) : pdfFiles.length ? (
          <div>
            <p className="font-medium text-slate-200">
              {pdfFiles.length.toLocaleString("pt-BR")} PDF(s) selecionado(s)
            </p>
            <p className="mt-1 text-sm text-slate-500">{formatTotalSize(pdfFiles)}</p>
            {pdfFiles.length > 350 && (
              <p className="mt-2 text-xs text-violet-400/90">
                Serão enviados em {Math.ceil(pdfFiles.length / 350)} lote(s) de até 350 PDFs
              </p>
            )}
            <p className="mt-2 truncate text-xs text-slate-600">
              {pdfFiles
                .slice(0, 4)
                .map((f) => f.name)
                .join(" · ")}
              {pdfFiles.length > 4 ? ` · +${pdfFiles.length - 4}…` : ""}
            </p>
          </div>
        ) : importing ? (
          <div>
            <p className="text-sm text-violet-300">Importação em background…</p>
            <p className="mt-1 text-xs text-slate-500">
              {progress?.message ?? "Processando PDFs no servidor"}
            </p>
          </div>
        ) : (
          <div>
            <p className="text-sm text-slate-300">Arraste a pasta ou PDFs para cá</p>
            <p className="mt-1 text-xs text-slate-500">
              Ideal para acervos grandes (centenas de NBRs/NRs licenciadas)
            </p>
          </div>
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        <input
          ref={filesInputRef}
          type="file"
          accept=".pdf,application/pdf"
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files?.length) requestPdfSelection(e.target.files);
          }}
        />
        <button
          type="button"
          onClick={handleSelectFolder}
          disabled={busy}
          className="rounded-xl border border-slate-600 px-4 py-2.5 text-sm font-medium text-slate-200 hover:bg-slate-800 disabled:opacity-50"
        >
          {scanningFolder ? "Lendo pasta…" : "Selecionar pasta"}
        </button>
        <button
          type="button"
          onClick={() => filesInputRef.current?.click()}
          disabled={busy}
          className="rounded-xl border border-slate-600 px-4 py-2.5 text-sm font-medium text-slate-200 hover:bg-slate-800 disabled:opacity-50"
        >
          Selecionar arquivos
        </button>
        <button
          type="button"
          onClick={handleImport}
          disabled={busy || !pdfFiles.length}
          className="rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-6 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
        >
          {importing ? "Importando lote…" : `Importar ${pdfFiles.length || ""} norma(s)`}
        </button>
        {(pdfFiles.length > 0 || resultSummary) && !importing && (
          <button
            type="button"
            onClick={handleClear}
            className="rounded-xl px-4 py-2.5 text-sm text-slate-400 hover:text-slate-200"
          >
            Limpar
          </button>
        )}
      </div>

      {!folderPickerAvailable && (
        <p className="mt-3 text-xs text-amber-400/90">
          Dica: use Chrome ou Edge para «Selecionar pasta» sem popup genérico do navegador, ou arraste
          a pasta direto na área tracejada.
        </p>
      )}

      {showProgress && progress && (
        <div className="mt-4 space-y-2 rounded-xl bg-slate-950/50 p-4 ring-1 ring-slate-800">
          <div className="flex items-center justify-between gap-3 text-xs">
            <span className="min-w-0 truncate text-slate-300">
              {progress.message ?? "Processando…"}
            </span>
            <span className="shrink-0 text-slate-500">{progress.percent ?? 0}%</span>
          </div>
          <div
            className="h-2 overflow-hidden rounded-full bg-slate-800"
            role="progressbar"
            aria-valuenow={progress.percent ?? 0}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Progresso da importação em lote"
          >
            <div
              className="h-full rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500 transition-all duration-300"
              style={{ width: `${progress.percent ?? 0}%` }}
            />
          </div>
        </div>
      )}

      {displayError && (
        <p className="mt-4 rounded-lg bg-red-950/40 px-4 py-3 text-sm text-red-300">{displayError}</p>
      )}
      {resultSummary && (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <p className="rounded-lg bg-emerald-950/30 px-4 py-3 text-sm text-emerald-300">
            {resultSummary}
          </p>
          {lastReport && (
            <button
              type="button"
              onClick={() => downloadTextFile(lastReport.csv, lastReport.filename)}
              className="rounded-xl border border-emerald-700/60 bg-emerald-950/40 px-4 py-2.5 text-sm font-medium text-emerald-300 hover:bg-emerald-950/60"
            >
              Baixar relatório CSV
            </button>
          )}
        </div>
      )}
      {errors.length > 0 && (
        <div className="mt-3 max-h-40 overflow-y-auto rounded-lg bg-slate-950/60 p-3 text-xs text-red-300">
          {errors.slice(0, 20).map((e, i) => (
            <p key={`${e.filename}-${i}`}>
              {e.filename}: {e.error}
            </p>
          ))}
          {errors.length > 20 && <p className="text-slate-500">+{errors.length - 20} erro(s)…</p>}
        </div>
      )}

      <ActionDialog
        open={confirmDialog.open}
        variant="confirm"
        title={confirmTitle}
        message={confirmMessage}
        confirmLabel="Carregar"
        cancelLabel="Cancelar"
        onConfirm={handleConfirmSelection}
        onCancel={handleCancelSelection}
      />
    </section>
  );
}
