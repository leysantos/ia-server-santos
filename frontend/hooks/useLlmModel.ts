"use client";

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "ia_llm_model";
const CHANGE_EVENT = "ia_llm_model_change";

export function useLlmModelSelection() {
  const [model, setModelState] = useState("auto");

  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) setModelState(saved);

    const onExternalChange = (e: Event) => {
      const detail = (e as CustomEvent<string>).detail;
      if (detail) setModelState(detail);
    };
    window.addEventListener(CHANGE_EVENT, onExternalChange);
    return () => window.removeEventListener(CHANGE_EVENT, onExternalChange);
  }, []);

  const setModel = useCallback((value: string) => {
    setModelState(value);
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, value);
      window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: value }));
    }
  }, []);

  return { model, setModel };
}

/** Valor para API: null quando auto */
export function llmModelForApi(model: string): string | undefined {
  if (!model || model === "auto") return undefined;
  return model;
}
