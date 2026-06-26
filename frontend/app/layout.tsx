import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Chatbot Panduan Akademik Unissula",
  description:
    "Tanya jawab seputar Panduan Akademik berbasis isi panduan resmi (RAG).",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="id">
      <body className="bg-gradient-to-b from-brand-50 to-slate-100 text-slate-900 dark:from-slate-950 dark:to-slate-900 dark:text-slate-100">
        {children}
      </body>
    </html>
  );
}
