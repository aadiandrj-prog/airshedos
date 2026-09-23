import type { ReactNode } from "react";

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "verified" | "caution" | "provider" | "ai" | "error" }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return <div className="empty-state"><span className="empty-symbol" aria-hidden="true">—</span><strong>{title}</strong><p>{children}</p></div>;
}

export function LoadingState({ children }: { children: ReactNode }) {
  return <div className="loading-state" role="status"><span className="loading-cue" aria-hidden="true" /><p>{children}</p></div>;
}
