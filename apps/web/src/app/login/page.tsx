"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { getGoogleLoginHref } from "@/lib/api";
import { LogIn } from "lucide-react";

function LoginForm() {
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/";
  const error = searchParams.get("error");
  const href = getGoogleLoginHref(next);

  return (
    <div className="mx-auto max-w-md px-6 py-16">
      <h1 className="text-2xl font-bold tracking-tight text-slate-900">
        Sign in
      </h1>
      <p className="mt-2 text-sm text-slate-600">
        Continue with Google to create and view lessons. Sessions use a secure
        HTTP-only cookie on this origin.
      </p>
      {error ? (
        <p className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          Sign-in failed: {error}
        </p>
      ) : null}
      <div className="mt-8">
        <Button asChild className="w-full gap-2" size="lg">
          <a href={href}>
            <LogIn className="h-4 w-4" />
            Continue with Google
          </a>
        </Button>
      </div>
      <p className="mt-6 text-center text-sm text-slate-500">
        <Link href="/" className="text-primary hover:underline">
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
      <main className="min-h-[60vh] bg-slate-50">
        <Suspense
          fallback={
            <div className="mx-auto max-w-md px-6 py-16 text-sm text-slate-500">
              Loading…
            </div>
          }
        >
          <LoginForm />
        </Suspense>
      </main>
    </>
  );
}
