"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Layers, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { AuthControls } from "@/components/layout/auth-controls";

export function Header() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-200/80 bg-white/85 shadow-[0_1px_0_0_rgba(15,23,42,0.04)] backdrop-blur-md supports-[backdrop-filter]:bg-white/75">
      <div className="mx-auto flex h-[3.25rem] max-w-6xl items-center justify-between px-6 sm:px-8">
        <Link
          href="/"
          className="flex items-center gap-2.5 transition-opacity hover:opacity-90"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm ring-1 ring-primary/10">
            <Layers className="h-4 w-4" />
          </div>
          <span className="text-[15px] font-semibold tracking-tight text-slate-900">
            VisualCS
          </span>
        </Link>

        <nav className="flex items-center gap-1">
          <AuthControls />
          <Link
            href="/"
            className={cn(
              "rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              pathname === "/"
                ? "bg-slate-100 text-slate-900"
                : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
            )}
          >
            Home
          </Link>
          <Link
            href="/new"
            className={cn(
              "flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              pathname === "/new"
                ? "bg-slate-100 text-slate-900"
                : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
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
