"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { getGoogleLoginHref } from "@/lib/api";
import { LogIn } from "lucide-react";

function LoginForm() {
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/";
  const error = searchParams.get("error");
  const href = getGoogleLoginHref(next);

  return (
    <div className="mx-auto w-full max-w-md px-6 py-16 sm:py-20">
      <p className="section-label mb-3 text-center">Account</p>
      <h1 className="text-center text-2xl font-semibold tracking-tight text-slate-900">
        Sign in
      </h1>
      <p className="mt-2 text-center text-sm leading-relaxed text-slate-600">
        Continue with Google to create and view lessons. Sessions use a secure
        HTTP-only cookie on this origin.
      </p>
      <Card className="mt-8 border-slate-200/90 shadow-sm ring-1 ring-slate-900/[0.03]">
        <CardContent className="pt-6">
          {error ? (
            <p className="mb-4 rounded-lg border border-red-200/90 bg-red-50 px-3 py-2.5 text-sm text-red-800">
              Sign-in failed: {error}
            </p>
          ) : null}
          <Button asChild className="w-full gap-2 shadow-sm" size="lg">
            <a href={href}>
              <LogIn className="h-4 w-4" />
              Continue with Google
            </a>
          </Button>
        </CardContent>
      </Card>
      <p className="mt-8 text-center text-sm text-slate-500">
        <Link
          href="/"
          className="font-medium text-primary hover:text-primary/90 hover:underline"
        >
          Back to home
        </Link>
      </p>
    </div>
  );
}

export default function LoginPage() {
  return (
    <>
      <Header />
      <main className="min-h-[65vh] flex-1 bg-[hsl(var(--page-bg))]">
        <Suspense
          fallback={
            <div className="mx-auto flex max-w-md flex-col items-center px-6 py-20 text-sm text-slate-500">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-primary/40" />
              <span className="mt-3">Loading…</span>
            </div>
          }
        >
          <LoginForm />
        </Suspense>
      </main>
      <Footer />
    </>
  );
}
