import type {
  ChatRequest,
  ChatResponse,
  HealthResponse,
  HistoryResponse,
  OrchestrateRequest,
  OrchestrateResponse,
} from "@/types/api";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Hook para auth futura — injeta token quando disponível */
function getAuthHeaders(): HeadersInit {
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

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...getAuthHeaders(),
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `Erro HTTP ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  chat(body: ChatRequest): Promise<ChatResponse> {
    return request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  orchestrate(body: OrchestrateRequest): Promise<OrchestrateResponse> {
    return request<OrchestrateResponse>("/orchestrate", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  history(limit = 50, conversationId?: string): Promise<HistoryResponse> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (conversationId) {
      params.set("conversation_id", conversationId);
    }
    return request<HistoryResponse>(`/history?${params.toString()}`);
  },

  health(): Promise<HealthResponse> {
    return request<HealthResponse>("/health");
  },
};

export { API_BASE_URL };
