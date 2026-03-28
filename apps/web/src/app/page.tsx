"use client";

import Link from "next/link";
import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  BookOpen,
  Upload,
  SlidersHorizontal,
  ArrowRight,
  Sparkles,
  Film,
  ShieldCheck,
  Layers,
  FileText,
  Zap,
  Palette,
} from "lucide-react";

const pipelineSteps = [
  {
    icon: FileText,
    title: "Input",
    description: "Type a CS topic or upload a PDF/PPTX. The system ingests and extracts concepts.",
    color: "text-blue-600 bg-blue-100",
  },
  {
    icon: Layers,
    title: "Plan",
    description: "AI creates a pedagogical lesson plan with learning objectives and scene structure.",
    color: "text-violet-600 bg-violet-100",
  },
  {
    icon: Palette,
    title: "Generate",
    description: "Scenes rendered with topic-specific diagrams, narration, and selective motion clips.",
    color: "text-emerald-600 bg-emerald-100",
  },
  {
    icon: SlidersHorizontal,
    title: "Edit",
    description: "Review every scene. Adjust narration, reorder, toggle Veo, regenerate any part.",
    color: "text-amber-600 bg-amber-100",
  },
  {
    icon: Film,
    title: "Render",
    description: "Final video with intro, transitions, synced audio, subtitles, and outro.",
    color: "text-pink-600 bg-pink-100",
  },
  {
    icon: ShieldCheck,
    title: "Evaluate",
    description: "Quality report with per-scene confidence, structural checks, and improvement suggestions.",
    color: "text-teal-600 bg-teal-100",
  },
];

const showcaseTopics = [
  {
    topic: "Rate Limiter",
    domain: "System Design",
    description: "Token bucket, leaky bucket, sliding window, distributed Redis rate limiting, and API gateway placement.",
    badge: "Best Demo",
  },
  {
    topic: "OS Deadlock",
    domain: "CS Concepts",
    description: "Four Coffman conditions, Resource Allocation Graphs, Banker's Algorithm, prevention vs. detection strategies.",
    badge: "Visual-Rich",
  },
  {
    topic: "Compiler Bottom-Up Parsing",
    domain: "CS Concepts",
    description: "Shift-reduce mechanics, LR parse tables, handle identification, AST construction, and parser variants.",
    badge: "Deep Dive",
  },
];

const moreSampleTopics = [
  "TCP Handshake",
  "Database Replication",
  "Recursion Trees",
  "Load Balancer",
  "Cache Eviction Policies",
  "Consistent Hashing",
  "Virtual Memory",
  "MapReduce",
];

const capabilities = [
  { label: "Topic to Video", desc: "Any CS topic → narrated lesson" },
  { label: "PDF/PPTX Upload", desc: "Research papers & slides → walkthrough" },
  { label: "Scene Editor", desc: "Edit narration, visuals, timing per scene" },
  { label: "Veo Motion", desc: "Selective 5s cinematic clips for key concepts" },
  { label: "Subtitles", desc: "Auto-generated SRT subtitle tracks" },
  { label: "Quality Report", desc: "Graded evaluation with confidence scores" },
];

export default function HomePage() {
  return (
    <>
      <Header />
      <main className="flex-1">
        {/* Hero */}
        <section className="relative overflow-hidden gradient-bg">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-blue-100/60 via-transparent to-transparent" />
          <div className="container relative py-24 md:py-32">
            <div className="mx-auto max-w-3xl text-center">
              <div className="mb-6 inline-flex items-center gap-2 rounded-full border bg-white/80 px-4 py-1.5 text-sm font-medium shadow-sm backdrop-blur">
                <Sparkles className="h-4 w-4 text-primary" />
                AI-Powered Visual Learning
              </div>
              <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl md:text-6xl">
                Learn CS{" "}
                <span className="gradient-text">Visually</span>
              </h1>
              <p className="mt-6 text-lg text-muted-foreground md:text-xl">
                Convert complex computer science topics into narrated, animated
                explainer videos. From compiler theory to system design — see it,
                hear it, understand it.
              </p>
              <div className="mt-10 flex items-center justify-center gap-4">
                <Button asChild size="lg" className="text-base">
                  <Link href="/new">
                    Get Started
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
                <Button asChild variant="outline" size="lg" className="text-base">
                  <Link href="#how-it-works">How It Works</Link>
                </Button>
              </div>
              <div className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
                {capabilities.map((c) => (
                  <span key={c.label} className="flex items-center gap-1.5">
                    <Zap className="h-3 w-3 text-primary" />
                    {c.label}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* How It Works — Pipeline */}
        <section id="how-it-works" className="container py-20">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight">
              How It Works
            </h2>
            <p className="mt-3 text-muted-foreground">
              A six-stage pipeline from topic to polished lesson — every step is transparent and editable
            </p>
          </div>
          <div className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-3 max-w-5xl mx-auto">
            {pipelineSteps.map((step, i) => (
              <Card
                key={step.title}
                className="group relative overflow-hidden border-border/50 transition-all hover:shadow-lg hover:border-primary/30"
              >
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-3">
                    <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${step.color}`}>
                      <step.icon className="h-5 w-5" />
                    </div>
                    <div>
                      <span className="text-xs font-bold text-muted-foreground">
                        STEP {i + 1}
                      </span>
                      <CardTitle className="text-base">{step.title}</CardTitle>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <CardDescription className="text-sm leading-relaxed">
                    {step.description}
                  </CardDescription>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        {/* Showcase Topics */}
        <section className="border-t bg-muted/30 py-20">
          <div className="container">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="text-3xl font-bold tracking-tight">
                Featured Demos
              </h2>
              <p className="mt-3 text-muted-foreground">
                Click any topic to generate a complete narrated lesson with intro, transitions, subtitles, and quality report
              </p>
            </div>
            <div className="mt-10 grid gap-4 md:grid-cols-3 max-w-4xl mx-auto">
              {showcaseTopics.map((item) => (
                <Link
                  key={item.topic}
                  href={`/new?topic=${encodeURIComponent(item.topic)}`}
                  className="group rounded-xl border bg-background p-5 shadow-sm transition-all hover:shadow-lg hover:border-primary/40 hover:-translate-y-0.5"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-primary/70">
                      {item.domain}
                    </span>
                    <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-bold text-primary">
                      <Sparkles className="h-2.5 w-2.5" />
                      {item.badge}
                    </span>
                  </div>
                  <h3 className="text-lg font-bold group-hover:text-primary transition-colors">
                    {item.topic}
                  </h3>
                  <p className="mt-1.5 text-sm text-muted-foreground leading-relaxed">
                    {item.description}
                  </p>
                  <div className="mt-3 flex items-center gap-1 text-xs font-medium text-primary opacity-0 group-hover:opacity-100 transition-opacity">
                    Try this demo
                    <ArrowRight className="h-3 w-3" />
                  </div>
                </Link>
              ))}
            </div>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              {moreSampleTopics.map((topic) => (
                <Link
                  key={topic}
                  href={`/new?topic=${encodeURIComponent(topic)}`}
                  className="group rounded-full border bg-background px-5 py-2.5 text-sm font-medium shadow-sm transition-all hover:border-primary hover:shadow-md hover:bg-primary/5"
                >
                  {topic}
                  <ArrowRight className="ml-2 inline h-3.5 w-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
                </Link>
              ))}
            </div>
          </div>
        </section>

        {/* Capabilities Grid */}
        <section className="container py-20">
          <div className="mx-auto max-w-2xl text-center mb-12">
            <h2 className="text-3xl font-bold tracking-tight">
              What You Get
            </h2>
            <p className="mt-3 text-muted-foreground">
              Every lesson is production-quality, not a slideshow
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 max-w-4xl mx-auto">
            {capabilities.map((cap) => (
              <div
                key={cap.label}
                className="flex items-start gap-3 rounded-lg border p-4 bg-card hover:shadow-md transition-shadow"
              >
                <Zap className="h-5 w-5 text-primary mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-semibold">{cap.label}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{cap.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* CTA */}
        <section className="border-t bg-gradient-to-b from-primary/5 to-background py-16">
          <div className="container text-center">
            <h2 className="text-2xl font-bold">Ready to build your lesson?</h2>
            <p className="mt-2 text-muted-foreground max-w-md mx-auto">
              Enter any CS topic or upload a research paper — your visual lesson is minutes away.
            </p>
            <div className="mt-6 flex items-center justify-center gap-4">
              <Button asChild size="lg">
                <Link href="/new">
                  Create Lesson
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
              <Button asChild variant="outline" size="lg">
                <Link href="/new?topic=Rate+Limiter">
                  <Sparkles className="mr-2 h-4 w-4" />
                  Try Rate Limiter Demo
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
