import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ASAGUS Scraper 3.0",
  description: "Intelligent scraping, enrichment and retrieval console"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
