import { getApiBaseUrl } from "@/lib/api-base";

export { getApiBaseUrl };

function networkErrorMessage(err: unknown): string {
  const base = getApiBaseUrl();
  const raw = err instanceof Error ? err.message : String(err);
  if (/failed to fetch|networkerror|load failed/i.test(raw)) {
    const viaProxy = base.includes("/api-backend");
    return (
      `Não foi possível conectar à API (${base}). ` +
      (viaProxy
        ? "Confirme que `make api` está rodando no servidor e reinicie o frontend (`npm run dev`) após alterar next.config."
        : "Confirme que `make api` está rodando, o portproxy Windows está ativo e que você acessa o sistema pelo mesmo IP da rede (ex.: http://172.22.3.234:3000).")
    );
  }
  return raw;
}

export async function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch (err) {
    throw new Error(networkErrorMessage(err));
  }
}

export function getAuthHeaders(): HeadersInit {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };

  if (typeof window !== "undefined") {
    const token = localStorage.getItem("ia_auth_token");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const tenantId = localStorage.getItem("ia_tenant_id");
    if (tenantId) {
      headers["X-Tenant-Id"] = tenantId;
    }
  }

  return headers;
}

export function getMultipartAuthHeaders(): HeadersInit {
  const headers: HeadersInit = {};

  if (typeof window !== "undefined") {
    const token = localStorage.getItem("ia_auth_token");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const tenantId = localStorage.getItem("ia_tenant_id");
    if (tenantId) {
      headers["X-Tenant-Id"] = tenantId;
    }
  }

  return headers;
}

export class BudgetVersionConflictError extends Error {
  readonly status = 409;
  readonly currentVersion?: number;

  constructor(message: string, currentVersion?: number) {
    super(message);
    this.name = "BudgetVersionConflictError";
    this.currentVersion = currentVersion;
  }
}

export async function throwIfNotOk(response: Response, path: string): Promise<void> {
  if (response.ok) return;
  const errorText = await response.text();
  if (
    response.status === 401 &&
    typeof window !== "undefined" &&
    !path.startsWith("/auth/login") &&
    !path.startsWith("/auth/status")
  ) {
    localStorage.removeItem("ia_auth_token");
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    if (!window.location.pathname.startsWith("/login")) {
      window.location.href = `/login?next=${next}`;
    }
  }
  if (response.status === 409) {
    try {
      const parsed = JSON.parse(errorText) as {
        detail?: { message?: string; current_version?: number } | string;
      };
      const detail = parsed.detail;
      if (detail && typeof detail === "object") {
        throw new BudgetVersionConflictError(
          detail.message ?? "Conflito de versão ao salvar orçamento",
          detail.current_version
        );
      }
    } catch (err) {
      if (err instanceof BudgetVersionConflictError) throw err;
    }
  }
  throw new Error(formatApiError(errorText, response.status));
}

export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await apiFetch(`${getApiBaseUrl()}${path}`, {
    ...options,
    headers: {
      ...getAuthHeaders(),
      ...options?.headers,
    },
  });

  if (!response.ok) {
    await throwIfNotOk(response, path);
  }

  return response.json() as Promise<T>;
}

export function formatApiError(errorText: string, status?: number): string {
  const trimmed = errorText.trim();
  if (!trimmed) return status ? `Erro HTTP ${status}` : "Erro desconhecido";
  try {
    const parsed = JSON.parse(trimmed) as { detail?: unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
    if (parsed.detail && typeof parsed.detail === "object" && "message" in parsed.detail) {
      const msg = (parsed.detail as { message?: string }).message;
      if (msg) return msg;
    }
    if (parsed.detail != null) return JSON.stringify(parsed.detail);
  } catch {
    /* texto puro */
  }
  if (/too many files/i.test(trimmed)) {
    return (
      "Limite de arquivos por requisição excedido. Reinicie a API (make api) e tente de novo — " +
      "acervos grandes são enviados automaticamente em lotes de 350 PDFs."
    );
  }
  return trimmed;
}

export async function parseFetchError(response: Response): Promise<string> {
  const text = await response.text();
  try {
    const json = JSON.parse(text) as { detail?: string | Array<{ msg?: string }> };
    if (typeof json.detail === "string") return json.detail;
    if (Array.isArray(json.detail)) {
      const parts = json.detail.map((d) => d.msg ?? "").filter(Boolean);
      if (parts.length) return parts.join("; ");
    }
  } catch {
    /* corpo não é JSON */
  }
  return text || `Erro HTTP ${response.status}`;
}

export async function downloadApiFile(path: string, fallbackFilename: string): Promise<void> {
  const response = await apiFetch(`${getApiBaseUrl()}${path}`, {
    headers: getMultipartAuthHeaders(),
  });
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(formatApiError(errorText, response.status));
  }
  const blob = await response.blob();
  const dispo = response.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^";\n]+)"?/.exec(dispo);
  const filename = match?.[1] ?? fallbackFilename;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function downloadTextFile(content: string, filename: string, mime = "text/csv;charset=utf-8"): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
