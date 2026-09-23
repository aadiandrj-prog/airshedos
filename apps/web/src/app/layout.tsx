import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AirshedOS | Air Operations Command Center",
  description:
    "Environmental evidence, provider outlook and manual officer review. A prototype with explicitly simulated jurisdiction handoffs.",
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
