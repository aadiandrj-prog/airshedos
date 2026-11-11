"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { clearResidentAttempts } from "../lib/resident-client";

export function SessionActions() {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  return <div className="session-actions"><button type="button" disabled={busy} onClick={async () => {
    clearResidentAttempts(); setBusy(true); setMessage("Signing out…");
    try {
      const nonce = await fetch("/api/app/csrf", { cache: "no-store", credentials: "same-origin" });
      if (nonce.status === 401) { router.replace("/sign-in"); router.refresh(); return; }
      if (!nonce.ok) throw new Error();
      const { csrf } = await nonce.json();
      const result = await fetch("/api/app/logout", { method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf }, body: "{}" });
      if (!result.ok) throw new Error();
      const { redirect } = await result.json();
      window.location.assign(redirect);
    } catch { setMessage("Sign-out could not complete. Please retry."); setBusy(false); }
  }}>Sign out</button><p role="status">{message}</p></div>;
}
