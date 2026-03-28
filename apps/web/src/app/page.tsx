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
          <div className="absolute inset-0 bg-gradient-to-b from-slate-50 to-white" />
          <div className="relative max-w-4xl mx-auto px-6 py-20 md:py-28 text-center">
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-1.5 text-sm font-medium text-slate-600 shadow-sm">
              <Sparkles className="h-3.5 w-3.5 text-primary" />
              Interactive CS Deep Dives
            </div>
            <h1 className="text-4xl font-extrabold tracking-tight text-slate-900 sm:text-5xl md:text-6xl">
              Learn CS by{" "}
              <span className="gradient-text">exploring diagrams</span>
            </h1>
            <p className="mt-5 text-lg text-slate-500 max-w-2xl mx-auto leading-relaxed">
              Type any CS topic. Get an interactive architecture diagram you can
              walk through step-by-step and discuss with Gemini via voice — in
              real time.
            </p>

            <div className="mt-8 flex items-center justify-center gap-3">
              <Button asChild size="lg" className="text-base h-12 px-6">
                <Link href="/new">
                  Start a Deep Dive
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
            </div>

            <div className="mt-8 flex flex-wrap justify-center gap-x-8 gap-y-3 text-sm text-slate-400">
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
        <section className="border-t bg-white py-16">
          <div className="max-w-4xl mx-auto px-6">
            <h2 className="text-center text-2xl font-bold text-slate-900 mb-2">
              Try a topic
            </h2>
            <p className="text-center text-slate-400 mb-10">
              Click any topic to generate an interactive lesson in minutes
            </p>

            <div className="grid gap-4 md:grid-cols-3">
              {showcaseTopics.map((item) => (
                <Link
                  key={item.topic}
                  href={`/new?topic=${encodeURIComponent(item.topic)}`}
                  className={`group rounded-xl border border-slate-200 bg-gradient-to-br ${item.gradient} p-5 transition-all hover:shadow-lg ${item.border} hover:-translate-y-0.5`}
                >
                  <p className="text-xs font-semibold uppercase tracking-wider text-primary/60 mb-1">
                    {item.domain}
                  </p>
                  <h3 className="text-lg font-bold text-slate-900 group-hover:text-primary transition-colors">
                    {item.topic}
                  </h3>
                  <p className="mt-2 text-sm text-slate-500 leading-relaxed">
                    {item.description}
                  </p>
                  <div className="mt-3 flex items-center gap-1 text-xs font-medium text-primary opacity-0 group-hover:opacity-100 transition-opacity">
                    Explore
                    <ArrowRight className="h-3 w-3" />
                  </div>
                </Link>
              ))}
            </div>

            <div className="mt-8 flex flex-wrap justify-center gap-2">
              {quickTopics.map((topic) => (
                <Link
                  key={topic}
                  href={`/new?topic=${encodeURIComponent(topic)}`}
                  className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 hover:border-primary/40 hover:text-primary hover:bg-primary/5 transition-all"
                >
                  {topic}
                </Link>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="border-t bg-slate-50 py-14">
          <div className="max-w-xl mx-auto px-6 text-center">
            <h2 className="text-xl font-bold text-slate-900">
              Any CS topic. Interactive in minutes.
            </h2>
            <p className="mt-2 text-slate-400 text-sm">
              Enter a topic or upload a research paper to get started.
            </p>
            <div className="mt-5">
              <Button asChild size="lg">
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
