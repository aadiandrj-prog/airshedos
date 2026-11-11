import type { Metadata } from "next";
import "./globals.css";
import "./pilot.css";

export const metadata: Metadata = {
  title: "AirshedOS | Report, understand, review",
  description:
    "Private resident reporting and approved-unit review, with advisory environmental evidence and explicit limitations.",
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
