/** Prefixo do proxy same-origin (Next.js → API local :8000). */
export const API_BACKEND_PROXY_PREFIX = "/api-backend";

/**
 * Resolve a URL base da API no browser.
 *
 * No browser usa sempre o proxy same-origin (`/api-backend`) para evitar CORS
 * e timeouts em requisições longas (batch analítico, generate-budget).
 * SSR continua usando `NEXT_PUBLIC_API_URL`.
 */
export function getApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  if (typeof window !== "undefined") {
    return `${window.location.origin}${API_BACKEND_PROXY_PREFIX}`;
  }

  return configured;
}
