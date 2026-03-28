"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Layers, Plus } from "lucide-react";
import { cn } from "@/lib/utils";

export function Header() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-200 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/80">
      <div className="max-w-6xl mx-auto px-6 flex h-14 items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Layers className="h-3.5 w-3.5" />
          </div>
          <span className="text-lg font-bold text-slate-900">VisualCS</span>
        </Link>

        <nav className="flex items-center gap-1">
          <Link
            href="/"
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              pathname === "/"
                ? "text-slate-900 bg-slate-100"
                : "text-slate-500 hover:text-slate-700 hover:bg-slate-50",
            )}
          >
            Home
          </Link>
          <Link
            href="/new"
            className={cn(
              "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              pathname === "/new"
                ? "text-slate-900 bg-slate-100"
                : "text-slate-500 hover:text-slate-700 hover:bg-slate-50",
            )}
          >
            <Plus className="h-3.5 w-3.5" />
            New
          </Link>
        </nav>
      </div>
    </header>
  );
}
