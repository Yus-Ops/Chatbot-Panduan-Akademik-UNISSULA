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
      <body className="bg-gradient-to-b from-brand-50 to-white text-slate-900">
        {children}
      </body>
    </html>
  );
}
