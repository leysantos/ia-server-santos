"use client";

import { useEffect, useState } from "react";
import { api } from "@/services/api";

interface ProjectFilePreviewProps {
  projectId: string;
  fileId: string;
  alt: string;
  className?: string;
}

export default function ProjectFilePreview({
  projectId,
  fileId,
  alt,
  className = "h-20 w-28 shrink-0 rounded-lg object-cover ring-1 ring-slate-700",
}: ProjectFilePreviewProps) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    setFailed(false);
    setSrc(null);

    api
      .fetchProjectFilePreview(projectId, fileId)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [projectId, fileId]);

  if (failed) {
    return (
      <div
        className={`flex items-center justify-center bg-slate-800 text-xs text-slate-500 ${className}`}
        title="Preview indisponível"
      >
        PDF
      </div>
    );
  }

  if (!src) {
    return (
      <div
        className={`animate-pulse bg-slate-800 ${className}`}
        aria-hidden
      />
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={alt} className={className} loading="lazy" />
  );
}
