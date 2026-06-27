import { Suspense } from "react";
import LoginPage from "./page.client";

export default function Page() {
  return (
    <Suspense fallback={<div className="flex min-h-dvh items-center justify-center text-slate-400">Carregando…</div>}>
      <LoginPage />
    </Suspense>
  );
}
