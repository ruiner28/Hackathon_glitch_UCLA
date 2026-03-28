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
} from "lucide-react";

const features = [
  {
    icon: BookOpen,
    title: "Topic to Lesson",
    description:
      "Enter any CS topic and get a structured, narrated video lesson with clear visuals and step-by-step explanations.",
  },
  {
    icon: Upload,
    title: "Upload Materials",
    description:
      "Upload your lecture PDFs or slides and transform them into engaging animated explainer videos automatically.",
  },
  {
    icon: SlidersHorizontal,
    title: "Scene-by-Scene Control",
    description:
      "Review and edit every scene — adjust narration, visuals, timing, and regenerate any part before final render.",
  },
];

const sampleTopics = [
  "Compiler Bottom-Up Parsing",
  "OS Deadlock",
  "TCP Handshake",
  "Rate Limiter",
  "Database Replication",
  "Recursion Trees",
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
                  <Link href="#features">Learn More</Link>
                </Button>
              </div>
            </div>
          </div>
        </section>

        {/* Features */}
        <section id="features" className="container py-20">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight">
              How It Works
            </h2>
            <p className="mt-3 text-muted-foreground">
              Three simple steps to create visual CS lessons
            </p>
          </div>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {features.map((feature, i) => (
              <Card
                key={feature.title}
                className="group relative overflow-hidden border-border/50 transition-all hover:shadow-lg hover:border-primary/30"
              >
                <CardHeader>
                  <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
                    <feature.icon className="h-6 w-6" />
                  </div>
                  <CardTitle className="text-lg">
                    <span className="text-muted-foreground mr-2">
                      {i + 1}.
                    </span>
                    {feature.title}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <CardDescription className="text-sm leading-relaxed">
                    {feature.description}
                  </CardDescription>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        {/* Sample Topics */}
        <section className="border-t bg-muted/30 py-20">
          <div className="container">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="text-3xl font-bold tracking-tight">
                Try a Topic
              </h2>
              <p className="mt-3 text-muted-foreground">
                Click any topic to jump straight into creating a lesson
              </p>
            </div>
            <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
              {sampleTopics.map((topic) => (
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
      </main>
      <Footer />
    </>
  );
}
