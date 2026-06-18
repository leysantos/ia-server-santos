"use client";

interface JsonViewerProps {
  data: unknown;
  title?: string;
  className?: string;
}

export default function JsonViewer({ data, title, className = "" }: JsonViewerProps) {
  return (
    <div className={`overflow-hidden rounded-xl border border-slate-700/60 bg-slate-950/80 ${className}`}>
      {title && (
        <div className="border-b border-slate-700/60 px-4 py-2 text-xs font-medium uppercase tracking-wider text-slate-400">
          {title}
        </div>
      )}
      <pre className="max-h-96 overflow-auto p-4 text-sm leading-relaxed text-emerald-300/90">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}
