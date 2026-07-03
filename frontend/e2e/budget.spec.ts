import { expect, test } from "@playwright/test";
import {
  installBudgetApiMocks,
  MOCK_CPU_DESCRIPTION,
  mockBudgetSession,
  seedBudgetSessionStorage,
} from "./fixtures/budget-api-mocks";

test.describe("Orçamento — smoke E2E", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      sessionStorage.clear();
      localStorage.clear();
    });
    await installBudgetApiMocks(page);
  });

  test("carrega página com toolbar e abas", async ({ page }) => {
    await page.goto("/budget");
    await expect(page.getByRole("heading", { name: "Orçamento de Obra" })).toBeVisible();
    await expect(page.getByTestId("budget-toolbar")).toBeVisible();
    await expect(page.getByTestId("budget-tab-historico")).toBeVisible();
    await expect(page.getByTestId("budget-tab-dados")).toBeVisible();
    await expect(page.getByTestId("budget-tab-etapas")).toBeVisible();
  });

  test("aba Histórico exibe gerador IA e lista salva", async ({ page }) => {
    await page.goto("/budget");
    await expect(page.getByRole("heading", { name: "Gerar orçamento com IA" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Gerar orçamento" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Obra piloto ·" }).first()).toBeVisible();
  });

  test("sem sessão, aba Dados mostra estado vazio", async ({ page }) => {
    await page.goto("/budget?tab=dados");
    await expect(page.getByRole("heading", { name: "Novo orçamento" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Ver orçamentos salvos" })).toBeVisible();
  });

  test("restaura sessão do sessionStorage e exibe Salvar", async ({ page }) => {
    const session = mockBudgetSession({ db_id: "saved-1", document_version: 2 });
    await seedBudgetSessionStorage(page, session);
    await installBudgetApiMocks(page, { session });

    await page.goto("/budget?tab=etapas");
    const saveBtn = page.getByTestId("budget-toolbar").getByRole("button", { name: /Salvar/ });
    await expect(saveBtn).toBeVisible();
    await expect(saveBtn).toContainText("v2");
    await expect(page.getByTestId("budget-autosave-status")).toContainText("Rascunho em sessão local");
  });

  test("aba Busca CPU carrega painel de consulta", async ({ page }) => {
    const session = mockBudgetSession();
    await seedBudgetSessionStorage(page, session);
    await installBudgetApiMocks(page, { session });

    await page.goto("/budget?tab=busca_cpu");
    await expect(page.getByTestId("budget-toolbar").getByRole("button", { name: /Salvar/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Prévia — composição aberta/ })).toBeVisible();
  });

  test("aba Auditoria abre com sessão ativa", async ({ page }) => {
    const session = mockBudgetSession();
    await seedBudgetSessionStorage(page, session);
    await installBudgetApiMocks(page, { session });

    await page.goto("/budget?tab=auditoria");
    await expect(page.getByTestId("budget-toolbar").getByRole("button", { name: /Salvar/ })).toBeVisible();
    await expect(page.getByTestId("budget-tab-auditoria")).toHaveAttribute("aria-selected", "true");
  });

  test("Busca CPU — lança composição na etapa (B13)", async ({ page }) => {
    const session = mockBudgetSession();
    await seedBudgetSessionStorage(page, session);
    await installBudgetApiMocks(page, { session });

    await page.goto("/budget?tab=busca_cpu");
    await page.getByPlaceholder("Ex: pavimento asfáltico, container…").fill("pavimento");
    await expect(page.getByRole("cell", { name: MOCK_CPU_DESCRIPTION })).toBeVisible();
    await page.getByRole("cell", { name: MOCK_CPU_DESCRIPTION }).click();
    await expect(page.getByText("Prévia do resultado")).toBeVisible();

    await expect(page.getByTestId("budget-cpu-launch-panel")).toBeVisible();
    await page.getByTestId("budget-cpu-launch-qty").fill("2");
    const launchResponse = page.waitForResponse(
      (r) => r.url().includes("/services") && r.request().method() === "POST"
    );
    await page.getByTestId("budget-cpu-launch-btn").click();
    const response = await launchResponse;
    expect(response.ok()).toBeTruthy();

    await page.getByTestId("budget-tab-etapas").click();
    await expect(page.getByRole("cell", { name: MOCK_CPU_DESCRIPTION })).toBeVisible({ timeout: 5000 });
  });

  test("aba Cronograma exibe controles e Gantt com sessão", async ({ page }) => {
    const session = mockBudgetSession();
    await seedBudgetSessionStorage(page, session);
    await installBudgetApiMocks(page, { session });

    await page.goto("/budget?tab=cronograma");
    await expect(page.getByTestId("budget-tab-cronograma")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("button", { name: "Sincronizar" })).toBeVisible();
    await expect(page.getByRole("button", { name: "CPM" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Serviço piloto/ }).first()).toBeVisible();
  });

  test("aba Analítico alterna ComD/SemD", async ({ page }) => {
    const session = mockBudgetSession();
    await seedBudgetSessionStorage(page, session);
    await installBudgetApiMocks(page, { session });

    await page.goto("/budget?tab=analitico");
    await expect(page.getByRole("heading", { name: "Orçamento analítico" })).toBeVisible();
    await expect(page.getByRole("article").getByText("Serviço piloto")).toBeVisible();

    const priceSelect = page.locator('select').filter({ hasText: "Com desoneração" });
    await priceSelect.selectOption("semd");
    await expect(priceSelect).toHaveValue("semd");
    await expect(page.getByText("Total SemD:").first()).toBeVisible();
  });
});

test.describe("Orçamento — CPQ e export live (B20/B21)", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      sessionStorage.clear();
      localStorage.clear();
    });
  });

  test("aba Dados — painel CPQ persiste margem e cliente", async ({ page }) => {
    const session = mockBudgetSession();
    await seedBudgetSessionStorage(page, session);
    await installBudgetApiMocks(page, { session });

    await page.goto("/budget?tab=dados");
    await expect(page.getByTestId("budget-commercial-panel")).toBeVisible();

    const patchResponse = page.waitForResponse(
      (r) => r.url().includes("/project") && r.request().method() === "PATCH",
      { timeout: 5000 }
    );
    await page.getByTestId("budget-commercial-margin").fill("12.5");
    await page.getByTestId("budget-commercial-client").fill("Cliente E2E Ltda");
    const response = await patchResponse;
    expect(response.ok()).toBeTruthy();
    const payload = (await response.request().postDataJSON()) as {
      commercial_margin_pct?: number;
      commercial_client?: string;
    };
    expect(payload.commercial_margin_pct).toBe(12.5);
    expect(payload.commercial_client).toBe("Cliente E2E Ltda");
    await expect(page.getByTestId("budget-commercial-preview")).toBeVisible();
  });

  test("toolbar — export PDF orc_sintetico retorna bytes PDF", async ({ page }) => {
    const session = mockBudgetSession();
    await seedBudgetSessionStorage(page, session);
    await installBudgetApiMocks(page, { session });

    await page.goto("/budget?tab=etapas");
    const responsePromise = page.waitForResponse(
      (r) => r.url().includes("/export/pdf/orc_sintetico") && r.request().method() === "GET"
    );
    await page.getByLabel("Tipo de documento").selectOption("orc_sintetico");
    await page.getByRole("button", { name: "Gerar PDF" }).click();
    const response = await responsePromise;
    expect(response.ok()).toBeTruthy();
    expect(response.headers()["content-type"]).toContain("application/pdf");
    expect(Number(response.headers()["content-length"] ?? 0)).toBeGreaterThan(10);
    expect(response.headers()["content-disposition"]).toContain("ORC_SINTETICO");
  });

  test("toolbar — export proposta comercial PDF e Excel", async ({ page }) => {
    const session = mockBudgetSession({
      project: {
        projeto: "Obra CPQ",
        commercial_margin_pct: 15,
        commercial_client: "Contratante E2E",
      },
    });
    await seedBudgetSessionStorage(page, session);
    await installBudgetApiMocks(page, { session });

    await page.goto("/budget?tab=dados");
    await page.getByLabel("Tipo de documento").selectOption("proposta_comercial");

    const pdfPromise = page.waitForResponse((r) => r.url().includes("/export/pdf/proposta_comercial"));
    await page.getByRole("button", { name: "Gerar PDF" }).click();
    const pdfResponse = await pdfPromise;
    expect(pdfResponse.ok()).toBeTruthy();
    expect(pdfResponse.headers()["content-type"]).toContain("application/pdf");
    expect(Number(pdfResponse.headers()["content-length"] ?? 0)).toBeGreaterThan(10);

    const xlsxPromise = page.waitForResponse((r) => r.url().includes("/export/xlsx/proposta_comercial"));
    await page.getByRole("button", { name: "Baixar Excel" }).click();
    const xlsxResponse = await xlsxPromise;
    expect(xlsxResponse.ok()).toBeTruthy();
    expect(xlsxResponse.headers()["content-type"]).toContain("spreadsheetml");
    expect(Number(xlsxResponse.headers()["content-length"] ?? 0)).toBeGreaterThan(4);
    expect(xlsxResponse.headers()["content-disposition"]).toContain("PROPOSTA_COMERCIAL");
  });

  test("toolbar — export PPD oficial .xlsm e pacote compliance", async ({ page }) => {
    const session = mockBudgetSession();
    await seedBudgetSessionStorage(page, session);
    await installBudgetApiMocks(page, { session });

    await page.goto("/budget?tab=etapas");

    const xlsmPromise = page.waitForResponse((r) => r.url().includes("/export/xlsm"));
    await page.getByTestId("budget-export-xlsm").click();
    const xlsmResponse = await xlsmPromise;
    expect(xlsmResponse.ok()).toBeTruthy();
    expect(xlsmResponse.headers()["content-type"]).toContain("macroEnabled");
    expect(Number(xlsmResponse.headers()["content-length"] ?? 0)).toBeGreaterThan(4);

    const compliancePromise = page.waitForResponse((r) => r.url().includes("/export/compliance-pack.json"));
    await page.getByTestId("budget-export-compliance").click();
    const complianceResponse = await compliancePromise;
    expect(complianceResponse.ok()).toBeTruthy();
    expect(complianceResponse.headers()["content-type"]).toContain("application/json");
  });

  test("aba Dados — painel compliance exibe checklist L1–L3", async ({ page }) => {
    const session = mockBudgetSession();
    await seedBudgetSessionStorage(page, session);
    await installBudgetApiMocks(page, { session });

    await page.goto("/budget?tab=dados");
    await expect(page.getByTestId("budget-compliance-panel")).toBeVisible();
    await expect(page.getByTestId("budget-compliance-item-L1")).toBeVisible();
    await expect(page.getByTestId("budget-compliance-item-L3")).toContainText("OK");
  });
});
