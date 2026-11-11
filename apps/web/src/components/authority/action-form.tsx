"use client";
import { useState } from "react";
export function ActionForm({ label, button, disabled, onSave, maxLength = 2000 }: {
  label: string; button: string; disabled: boolean; maxLength?: number;
  onSave: (text: string) => Promise<boolean>;
}) {
  const [text, setText] = useState("");
  return <form onSubmit={async (event) => { event.preventDefault(); if (text.trim() && await onSave(text)) setText(""); }}>
    <label>{label}<textarea required maxLength={maxLength} value={text} disabled={disabled} onChange={(e) => setText(e.target.value)} /></label>
    <button type="submit" disabled={disabled || !text.trim()}>{button}</button>
  </form>;
}
