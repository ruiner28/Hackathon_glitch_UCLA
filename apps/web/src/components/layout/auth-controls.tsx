"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authLogout, fetchAuthMe, type AuthUser } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Loader2, LogIn, LogOut } from "lucide-react";

export function AuthControls() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    fetchAuthMe()
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function logout() {
    setBusy(true);
    try {
      await authLogout();
      setUser(null);
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  if (user === undefined) {
    return (
      <span className="flex h-8 w-8 items-center justify-center text-slate-400">
        <Loader2 className="h-4 w-4 animate-spin" />
      </span>
    );
  }

  if (!user) {
    return (
      <Button variant="outline" size="sm" asChild className="gap-1.5">
        <Link href="/login">
          <LogIn className="h-3.5 w-3.5" />
          Sign in
        </Link>
      </Button>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <span
        className="hidden max-w-[10rem] truncate text-xs text-slate-600 sm:inline"
        title={user.email}
      >
        {user.name || user.email}
      </span>
      <Button
        variant="ghost"
        size="sm"
        className="gap-1.5 text-slate-600"
        disabled={busy}
        onClick={() => void logout()}
      >
        {busy ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <LogOut className="h-3.5 w-3.5" />
        )}
        <span className="hidden sm:inline">Sign out</span>
      </Button>
    </div>
  );
}
