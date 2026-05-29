import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "OpsFlow AI",
  description: "AI workflow automation platform for ops teams",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
