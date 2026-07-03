import { expect, test } from "@playwright/test";

/**
 * E2E contra backend FastAPI real (sem mocks de orçamento).
 * Requer: backend em :8000 + RUN_E2E_REAL_BACKEND=1
 */
const LIVE = process.env.RUN_E2E_REAL_BACKEND === "1";
const API_BASE = process.env.PLAYWRIGHT_API_BASE ?? "http://localhost:8000";
const AUTH_USER = process.env.PLAYWRIGHT_AUTH_USER ?? "admin";
const AUTH_PASS = process.env.PLAYWRIGHT_AUTH_PASS ?? "Admin@2026!";

async function authHeaders(request: import("@playwright/test").APIRequestContext) {
  const login = await request.post(`${API_BASE}/auth/login`, {
    data: { username: AUTH_USER, password: AUTH_PASS },
  });
  expect(login.ok()).toBeTruthy();
  const token = (await login.json()).access_token as string;
  return { Authorization: `Bearer ${token}` };
}

test.describe("Orçamento — export API real (B25)", () => {
  test.skip(!LIVE, "Defina RUN_E2E_REAL_BACKEND=1 com backend em :8000");

  test("export PDF, xlsm e compliance-pack via API real", async ({ request }) => {
    const health = await request.get(`${API_BASE}/health`);
    expect(health.ok()).toBeTruthy();

    const headers = await authHeaders(request);
    const created = await request.post(`${API_BASE}/pricing/budget/new-template`, { headers });
    expect(created.ok()).toBeTruthy();
    const sid = (await created.json()).session_id as string;

    const pdf = await request.get(`${API_BASE}/pricing/budget/${sid}/export/pdf/orc_sintetico`, { headers });
    expect(pdf.ok()).toBeTruthy();
    const pdfBody = await pdf.body();
    expect(pdfBody.subarray(0, 4).toString()).toBe("%PDF");

    const xlsm = await request.get(`${API_BASE}/pricing/budget/${sid}/export/xlsm?sync=true`, { headers });
    if (xlsm.status() === 404) {
      test.info().annotations.push({
        type: "notice",
        description:
          "PPD .xlsm ignorado — copie um template para planilhas-exemplos/ (ppd_seminf_abril_2026.xlsm, v8.1 ou R01)",
      });
    } else {
      expect(xlsm.ok()).toBeTruthy();
      const xlsmBody = await xlsm.body();
      expect(xlsmBody.subarray(0, 2).toString()).toBe("PK");
    }

    const compliance = await request.get(
      `${API_BASE}/pricing/budget/${sid}/export/compliance-pack.json`,
      { headers }
    );
    expect(compliance.ok()).toBeTruthy();
    const pack = await compliance.json();
    expect(pack.checklist_lei_14133?.length).toBeGreaterThan(4);

    const bdiVal = await request.get(`${API_BASE}/pricing/budget/${sid}/bdi/validation`, { headers });
    expect(bdiVal.ok()).toBeTruthy();
    expect(["ok", "warning", "error"]).toContain((await bdiVal.json()).status);
  });
});
