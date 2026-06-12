import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "ASAGUS Mailer — Cold Email Automation",
  description: "Production-grade cold email automation system with multi-sender rotation, A/B testing, follow-ups, reply detection, and deep analytics.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="flex h-screen overflow-hidden bg-[#f4f5f9]">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <div className="p-6 max-w-[1400px] mx-auto">
            {children}
          </div>
        </main>
      </body>
    </html>
  );
}
