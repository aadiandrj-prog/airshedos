import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AirshedOS | Air Operations Command Center",
  description:
    "Phase 1A local demo of an evidence-led pollution incident command center.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
