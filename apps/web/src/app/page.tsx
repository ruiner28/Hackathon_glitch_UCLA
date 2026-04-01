"use client";

import Link from "next/link";
import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { Button } from "@/components/ui/button";
import { ArrowRight, Sparkles, Mic, BookOpen, Layers } from "lucide-react";

const showcaseTopics = [
  {
    topic: "Rate Limiter",
    domain: "System Design",
    description:
      "Token bucket, sliding window, Redis, API gateway — interactive diagram with voice Q&A.",
    gradient: "from-blue-500/10 to-indigo-500/10",
    border: "hover:border-blue-300",
  },
  {
    topic: "OS Deadlock",
    domain: "CS Concepts",
    description:
      "Coffman conditions, Resource Allocation Graphs, Banker's Algorithm, prevention vs detection.",
    gradient: "from-violet-500/10 to-purple-500/10",
    border: "hover:border-violet-300",
  },
  {
    topic: "Compiler Bottom-Up Parsing",
    domain: "CS Concepts",
    description:
      "Shift-reduce, LR parse tables, handle identification, AST construction.",
    gradient: "from-emerald-500/10 to-teal-500/10",
    border: "hover:border-emerald-300",
  },
];

const quickTopics = [
  "TCP Handshake",
  "Database Replication",
  "Load Balancer",
  "Consistent Hashing",
  "Virtual Memory",
  "MapReduce",
  "Cache Eviction",
  "Recursion Trees",
];

export default function HomePage() {
  return (
    <>
      <Header />
      <main className="flex-1">
        {/* Hero */}
        <section className="relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-b from-slate-50 via-white to-[hsl(var(--page-bg))]" />
          <div className="relative mx-auto max-w-4xl px-6 py-20 text-center md:py-28">
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-slate-200/90 bg-white/90 px-4 py-1.5 text-sm font-medium text-slate-600 shadow-sm ring-1 ring-slate-900/5">
              <Sparkles className="h-3.5 w-3.5 text-primary" />
              Interactive CS deep dives
            </div>
            <h1 className="text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl md:text-[3.25rem] md:leading-[1.1]">
              Learn CS by{" "}
              <span className="gradient-text">exploring diagrams</span>
            </h1>
            <p className="mx-auto mt-5 max-w-2xl text-lg leading-relaxed text-slate-600">
              Type any CS topic. Get an interactive architecture diagram you can
              walk through step-by-step and discuss with Gemini via voice — in
              real time.
            </p>

            <div className="mt-9 flex items-center justify-center gap-3">
              <Button asChild size="lg" className="h-12 px-7 text-base shadow-sm">
                <Link href="/new">
                  Start a Deep Dive
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
            </div>

            <div className="mt-10 flex flex-wrap justify-center gap-x-8 gap-y-3 text-sm text-slate-500">
              <span className="flex items-center gap-1.5">
                <Layers className="h-3.5 w-3.5" />
                Interactive diagrams
              </span>
              <span className="flex items-center gap-1.5">
                <Mic className="h-3.5 w-3.5" />
                Voice Q&A with Gemini Live
              </span>
              <span className="flex items-center gap-1.5">
                <BookOpen className="h-3.5 w-3.5" />
                Step-by-step walkthrough
              </span>
            </div>
          </div>
        </section>

        {/* Featured Topics */}
        <section className="border-t border-slate-200/80 bg-white py-16 md:py-20">
          <div className="mx-auto max-w-5xl px-6 sm:px-8">
            <p className="section-label mb-2 text-center">Templates</p>
            <h2 className="mb-2 text-center text-2xl font-semibold tracking-tight text-slate-900">
              Try a topic
            </h2>
            <p className="mb-10 text-center text-sm text-slate-500">
              Click any topic to generate an interactive lesson in minutes
            </p>

            <div className="grid gap-4 md:grid-cols-3">
              {showcaseTopics.map((item) => (
                <Link
                  key={item.topic}
                  href={`/new?topic=${encodeURIComponent(item.topic)}`}
                  className={`group rounded-2xl border border-slate-200/90 bg-gradient-to-br ${item.gradient} p-6 shadow-sm ring-1 ring-slate-900/[0.04] transition-all hover:-translate-y-0.5 hover:shadow-md ${item.border}`}
                >
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-primary/70">
                    {item.domain}
                  </p>
                  <h3 className="text-lg font-semibold text-slate-900 transition-colors group-hover:text-primary">
                    {item.topic}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-600">
                    {item.description}
                  </p>
                  <div className="mt-4 flex items-center gap-1 text-xs font-semibold text-primary opacity-0 transition-opacity group-hover:opacity-100">
                    Explore
                    <ArrowRight className="h-3 w-3" />
                  </div>
                </Link>
              ))}
            </div>

            <div className="mt-10 flex flex-wrap justify-center gap-2">
              {quickTopics.map((topic) => (
                <Link
                  key={topic}
                  href={`/new?topic=${encodeURIComponent(topic)}`}
                  className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 shadow-sm transition-all hover:border-primary/30 hover:bg-primary/[0.04] hover:text-primary"
                >
                  {topic}
                </Link>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="border-t border-slate-200/80 bg-[hsl(var(--page-bg))] py-16">
          <div className="mx-auto max-w-xl px-6 text-center sm:px-8">
            <p className="section-label mb-3">Get started</p>
            <h2 className="text-xl font-semibold tracking-tight text-slate-900">
              Any CS topic. Interactive in minutes.
            </h2>
            <p className="mt-2 text-sm text-slate-500">
              Enter a topic or upload a research paper to get started.
            </p>
            <div className="mt-6">
              <Button asChild size="lg" className="shadow-sm">
                <Link href="/new">
                  Create Lesson
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
