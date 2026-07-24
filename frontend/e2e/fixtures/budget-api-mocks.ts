import type { Page, Route } from "@playwright/test";
import type { BudgetSessionResponse, OpenCompositionDetail } from "@/types/api";

const NOW = "2026-06-20T12:00:00.000Z";

export const MOCK_CPU_CODE = "95995";
export const MOCK_CPU_DESCRIPTION = "Pavimento asfáltico E2E";

export const mockOpenComposition = (): OpenCompositionDetail => ({
  code: MOCK_CPU_CODE,
  description: MOCK_CPU_DESCRIPTION,
  unit: "m²",
  total_price: 125.5,
  total_price_sem: 118.2,
  analytical_total_com: 125.5,
  analytical_total_sem: 118.2,
  items: [],
  source: "sinapi",
});

export function mockBudgetSession(overrides: Partial<BudgetSessionResponse> = {}): BudgetSessionResponse {
  return {
    session_id: "e2e-session-1",
    title: "Orçamento E2E",
    rows: [
      {
        row_id: "row-etapa-1",
        code: "1",
        name: "Etapa fundação",
        level: 0,
        quantity: 1,
        unit: "vb",
        unit_cost: 0,
        unit_price: 0,
        total_price: 0,
        source_base: "manual",
        source_code: "",
        item_type: "etapa",
        row_type: "ETAPA",
        editable: true,
      },
      {
        row_id: "row-svc-1",
        code: "1.1",
        name: "Serviço piloto",
        level: 1,
        quantity: 10,
        unit: "m²",
        unit_cost: 100,
        unit_price: 120,
        total_price: 1200,
        unit_cost_semd: 95,
        unit_price_semd: 114,
        total_price_semd: 1140,
        source_base: "sinapi",
        source_code: MOCK_CPU_CODE,
        parent_code: "1",
        item_type: "servico",
        row_type: "S",
        editable: true,
      },
    ],
    items: [],
    grand_total: 1200,
    currency: "BRL",
    calculation_memory: [],
    source_priority: ["sinapi"],
    intent: {},
    created_at: NOW,
    updated_at: NOW,
    schedule: {
      project_start: "2026-07-01",
      project_end: "2026-09-30",
      tasks: [
        {
          task_id: "task-1",
          budget_row_id: "row-etapa-1",
          budget_code: "1",
          name: "Etapa fundação",
          row_type: "ETAPA",
          duration_days: 30,
          is_summary: true,
          early_start: "2026-07-01",
          early_finish: "2026-09-30",
        },
        {
          task_id: "task-2",
          budget_row_id: "row-svc-1",
          budget_code: "1.1",
          name: "Serviço piloto",
          row_type: "S",
          parent_code: "1",
          duration_days: 15,
          is_summary: false,
          is_critical: true,
          early_start: "2026-07-01",
          early_finish: "2026-07-15",
        },
      ],
      links: [],
    },
    ...overrides,
  };
}

function apiPath(url: string): string {
  const pathname = new URL(url).pathname;
  if (pathname.startsWith("/api-backend/")) {
    return pathname.slice("/api-backend".length);
  }
  return pathname;
}

async function fulfillJson(route: Route, body: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

export interface BudgetApiMockOptions {
  session?: BudgetSessionResponse | null;
  savedItems?: Array<{ id: string; title: string; updated_at: string; grand_total: number }>;
}

export async function installBudgetApiMocks(page: Page, options: BudgetApiMockOptions = {}): Promise<void> {
  let liveSession = options.session ?? null;
  const savedItems = options.savedItems ?? [
    { id: "saved-1", title: "Obra piloto", updated_at: NOW, grand_total: 50000 },
  ];

  await page.route(/\/(auth\/|health|pricing\/|models\/)/, async (route) => {
    const path = apiPath(route.request().url());
    const method = route.request().method();

    if (path === "/auth/status") {
      return fulfillJson(route, { auth_enabled: false });
    }

    if (path === "/health") {
      return fulfillJson(route, {
        status: "ok",
        models: { installed_llm: "phi3:mini · nomic-embed-text" },
      });
    }

    if (path === "/pricing/bdi/types") {
      return fulfillJson(route, {
        types: [{ id: "RF", label: "Reforma" }],
        default: "RF",
      });
    }

    if (path === "/pricing/providers") {
      return fulfillJson(route, { providers: [{ id: "sinapi", label: "SINAPI" }] });
    }

    if (path === "/pricing/sync/bank/references") {
      return fulfillJson(route, {
        references: [{ reference: "2025-01", provider: "sinapi", label: "2025-01" }],
      });
    }

    if (path === "/pricing/sync/status") {
      return fulfillJson(route, { sources: [], active_reference: "2025-01" });
    }

    if (path.includes("/open-compositions/search") && method === "GET") {
      const comp = mockOpenComposition();
      return fulfillJson(route, {
        items: [
          {
            code: comp.code,
            description: comp.description,
            unit: comp.unit,
            total_price: comp.total_price,
            total_price_sem: comp.total_price_sem,
            match_kind: "description",
          },
        ],
      });
    }

    if (path.includes("/compositions/batch") && method === "GET") {
      const comp = mockOpenComposition();
      return fulfillJson(route, {
        session_id: "mock-session",
        snapshots: { [`${comp.code}|2025-01|SP`]: comp },
        total: 1,
        from_db: 0,
        from_bank: 1,
        missing: [],
      });
    }

    if (path.includes("/composition/") && method === "GET") {
      return fulfillJson(route, mockOpenComposition());
    }

    if (/\/pricing\/budget\/[^/]+\/services$/.test(path) && method === "POST") {
      const body = (route.request().postDataJSON() ?? {}) as {
        etapa_code?: string;
        code?: string;
        description?: string;
        quantity?: number;
      };
      const base = liveSession ?? mockBudgetSession();
      const qty = body.quantity ?? 1;
      const newRow = {
        row_id: "row-launched",
        code: `${body.etapa_code ?? "1"}.2`,
        name: body.description ?? "Composição lançada",
        level: 1,
        quantity: qty,
        unit: "m²",
        unit_cost: 125.5,
        unit_price: 150,
        unit_price_semd: 142,
        total_price: 150 * qty,
        total_price_semd: 142 * qty,
        source_base: "sinapi",
        source_code: body.code ?? MOCK_CPU_CODE,
        parent_code: body.etapa_code ?? "1",
        item_type: "servico",
        row_type: "S",
        editable: true,
      };
      liveSession = {
        ...base,
        rows: [...(base.rows ?? []), newRow],
        grand_total: (base.grand_total ?? 0) + newRow.total_price,
      };
      return fulfillJson(route, liveSession);
    }

    if (path === "/pricing/budget/saved" && method === "GET") {
      return fulfillJson(route, { items: savedItems });
    }

    if (path === "/pricing/budget/restore" && method === "POST") {
      const body = route.request().postDataJSON() as { payload?: BudgetSessionResponse };
      liveSession = body?.payload ?? liveSession ?? mockBudgetSession();
      return fulfillJson(route, liveSession);
    }

    if (path === "/pricing/budget/new-template" && method === "POST") {
      liveSession = liveSession ?? mockBudgetSession({ title: "Novo template E2E" });
      return fulfillJson(route, liveSession);
    }

    if (path.startsWith("/pricing/budget/saved/") && method === "GET") {
      const id = path.split("/").pop() ?? "saved-1";
      return fulfillJson(route, {
        ...(liveSession ?? mockBudgetSession()),
        db_id: id,
        document_version: 1,
      });
    }

    if (path.startsWith("/pricing/budget/saved/") && method === "PUT") {
      const id = path.split("/").pop() ?? "saved-1";
      const body = route.request().postDataJSON() as { payload?: BudgetSessionResponse; expected_version?: number };
      liveSession = {
        ...(body.payload ?? liveSession ?? mockBudgetSession()),
        db_id: id,
        document_version: (body.expected_version ?? 0) + 1,
      };
      return fulfillJson(route, liveSession);
    }

    if (path.endsWith("/schedule/sync") && method === "POST") {
      liveSession = liveSession ?? mockBudgetSession();
      return fulfillJson(route, liveSession);
    }

    if (path.endsWith("/audit") && method === "GET") {
      return fulfillJson(route, { items: [] });
    }

    if (path.includes("/export/pdf/") && method === "GET") {
      const docKey = path.split("/export/pdf/")[1]?.split("?")[0] ?? "orc_sintetico";
      const pdfBody = Buffer.from(`%PDF-1.4\n% mock export ${docKey}\n%%EOF`);
      return route.fulfill({
        status: 200,
        contentType: "application/pdf",
        headers: {
          "Content-Disposition": `attachment; filename="${docKey.toUpperCase()}_e2e.pdf"`,
          "Content-Length": String(pdfBody.length),
        },
        body: pdfBody,
      });
    }

    if (path.includes("/export/xlsx/") && method === "GET") {
      const docKey = path.split("/export/xlsx/")[1]?.split("?")[0] ?? "orc_sintetico";
      const xlsxBody = Buffer.from("PK\x03\x04mock-xlsx-export");
      return route.fulfill({
        status: 200,
        contentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers: {
          "Content-Disposition": `attachment; filename="${docKey.toUpperCase()}_e2e.xlsx"`,
          "Content-Length": String(xlsxBody.length),
        },
        body: xlsxBody,
      });
    }

    if (path.endsWith("/export/compliance-pack.json") && method === "GET") {
      return fulfillJson(route, {
        session_id: liveSession?.session_id ?? "e2e-session-1",
        generated_at: NOW,
        bdi_validation_status: "ok",
        export_official_xlsm: false,
        checklist_lei_14133: [
          { id: "L1", item: "Memória de cálculo (MCQ) disponível", status: "ok" },
          { id: "L2", item: "Orçamento analítico ComD/SemD", status: "ok" },
          { id: "L3", item: "BDI documentado e validado vs edital", status: "ok" },
          { id: "L6", item: "Publicação PNCP", status: "manual" },
        ],
      });
    }

    if (path.includes("/export/xlsm") && method === "GET") {
      const xlsmBody = Buffer.from("PK\x03\x04mock-xlsm-official");
      return route.fulfill({
        status: 200,
        contentType: "application/vnd.ms-excel.sheet.macroEnabled.12",
        headers: {
          "Content-Disposition": 'attachment; filename="PPD_e2e.xlsm"',
          "Content-Length": String(xlsmBody.length),
        },
        body: xlsmBody,
      });
    }

    if (path.endsWith("/bdi/validation") && method === "GET") {
      return fulfillJson(route, {
        status: "ok",
        profile_id: "seminf_table",
        profile_label: "SEMINF — tabela por tipo de obra",
        applied_rates: { com_desoneracao: 0.2426, sem_desoneracao: 0.2289 },
        reference_rates: { com_desoneracao: 0.2426, sem_desoneracao: 0.2289 },
        issue_count: 0,
        error_count: 0,
        warning_count: 0,
        issues: [],
        valid_for_edital: true,
      });
    }

    if (path.endsWith("/project") && method === "PATCH") {
      const body = (route.request().postDataJSON() ?? {}) as Record<string, unknown>;
      const base = liveSession ?? mockBudgetSession();
      liveSession = {
        ...base,
        project: {
          ...base.project,
          ...(body as Partial<BudgetSessionResponse["project"]>),
        },
        updated_at: NOW,
      };
      return fulfillJson(route, liveSession);
    }

    if (path.startsWith("/pricing/budget/") && method === "GET") {
      return fulfillJson(route, liveSession ?? mockBudgetSession());
    }

    return route.continue();
  });
}

export async function seedBudgetSessionStorage(page: Page, session: BudgetSessionResponse): Promise<void> {
  await page.addInitScript(
    ([key, payload]) => {
      sessionStorage.setItem(key, payload);
    },
    ["iaserver.budget.session", JSON.stringify(session)] as const
  );
}
