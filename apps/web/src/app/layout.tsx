import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "VisualCS - Visual Computer Science Learning",
  description:
    "Convert complex CS topics into narrated, animated explainer videos. Learn visually with AI-generated lessons.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="scroll-smooth">
      <body
        className={`${inter.className} min-h-screen text-slate-900 selection:bg-primary/15 selection:text-slate-900`}
      >
        <div className="flex min-h-screen flex-col">{children}</div>
      </body>
    </html>
  );
}
