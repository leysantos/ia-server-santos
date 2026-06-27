/** Prefixo do proxy same-origin (Next.js → API local :8000). */
export const API_BACKEND_PROXY_PREFIX = "/api-backend";

/**
 * Resolve a URL base da API no browser.
 *
 * - **localhost** — usa `NEXT_PUBLIC_API_URL` (padrão `http://localhost:8000`).
 * - **LAN / Cloudflare / outro host** — usa proxy same-origin (`/api-backend`),
 *   para não depender da porta 8000 exposta na rede (só :3000 + portproxy).
 */
export function getApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  if (typeof window === "undefined") {
    return configured;
  }

  const pageHost = window.location.hostname;
  const isLocalPage = pageHost === "localhost" || pageHost === "127.0.0.1";

  if (!isLocalPage) {
    return `${window.location.origin}${API_BACKEND_PROXY_PREFIX}`;
  }

  try {
    const url = new URL(configured);
    const configHost = url.hostname;
    const isLocalConfig = configHost === "localhost" || configHost === "127.0.0.1";
    if (isLocalConfig) {
      const port = url.port || "8000";
      return `${url.protocol}//${pageHost}:${port}`;
    }
    return configured;
  } catch {
    return configured;
  }
}
