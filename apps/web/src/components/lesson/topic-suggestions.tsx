"use client";

import { cn } from "@/lib/utils";
import { Sparkles } from "lucide-react";

interface TopicSuggestion {
  label: string;
  domain: string;
  featured?: boolean;
}

const FEATURED: TopicSuggestion[] = [
  { label: "Rate Limiter", domain: "system_design", featured: true },
  { label: "OS Deadlock", domain: "cs_concepts", featured: true },
  { label: "Compiler Bottom-Up Parsing", domain: "cs_concepts", featured: true },
];

const SUGGESTIONS: Record<string, TopicSuggestion[]> = {
  "System Design": [
    { label: "TCP Handshake", domain: "system_design" },
    { label: "Database Replication", domain: "system_design" },
    { label: "Load Balancer", domain: "system_design" },
    { label: "Consistent Hashing", domain: "system_design" },
    { label: "Event-Driven Architecture", domain: "system_design" },
    { label: "Message Queue Patterns", domain: "system_design" },
    { label: "CDN Architecture", domain: "system_design" },
  ],
  "CS Concepts": [
    { label: "Recursion Trees", domain: "cs_concepts" },
    { label: "B+ Tree Insertion", domain: "cs_concepts" },
    { label: "Cache Eviction Policies", domain: "cs_concepts" },
    { label: "Garbage Collection", domain: "cs_concepts" },
    { label: "Context Switching", domain: "cs_concepts" },
    { label: "Virtual Memory Paging", domain: "cs_concepts" },
  ],
};

interface TopicSuggestionsProps {
  onSelect: (topic: string, domain?: string) => void;
  selectedTopic?: string;
}

export function TopicSuggestions({
  onSelect,
  selectedTopic,
}: TopicSuggestionsProps) {
  return (
    <div className="space-y-4">
      {/* Featured showcase topics */}
      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2 flex items-center gap-1.5">
          <Sparkles className="h-3 w-3" />
          Showcase Demos
        </h4>
        <div className="flex flex-wrap gap-2">
          {FEATURED.map((t) => (
            <button
              key={t.label}
              type="button"
              onClick={() => onSelect(t.label, t.domain)}
              className={cn(
                "rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-all hover:shadow-md",
                selectedTopic === t.label
                  ? "border-primary bg-primary text-primary-foreground shadow-sm"
                  : "border-primary/30 bg-primary/5 text-primary hover:bg-primary/10 hover:border-primary/50"
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {Object.entries(SUGGESTIONS).map(([category, topics]) => (
        <div key={category}>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
            {category}
          </h4>
          <div className="flex flex-wrap gap-2">
            {topics.map((t) => (
              <button
                key={t.label}
                type="button"
                onClick={() => onSelect(t.label, t.domain)}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs font-medium transition-all hover:shadow-sm",
                  selectedTopic === t.label
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-background text-foreground hover:border-primary/40 hover:bg-primary/5"
                )}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
