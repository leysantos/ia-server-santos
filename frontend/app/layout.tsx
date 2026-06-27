import type { Metadata } from "next";
import localFont from "next/font/local";
import AppChrome from "@/components/AppChrome";
import "./globals.css";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "IA Server Santos",
  description: "SaaS de engenharia multidisciplinar com IA e RAG v2",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body className={`${geistSans.variable} min-h-screen bg-surface font-sans antialiased`}>
        <AppChrome>{children}</AppChrome>
      </body>
    </html>
  );
}
