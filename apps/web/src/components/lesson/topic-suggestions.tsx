"use client";

import { cn } from "@/lib/utils";

const SUGGESTIONS = {
  "CS Concepts": [
    "Compiler Bottom-Up Parsing",
    "OS Deadlock",
    "Recursion Trees",
    "B+ Tree Insertion",
    "Cache Eviction Policies",
    "Garbage Collection",
    "Context Switching",
    "Virtual Memory Paging",
  ],
  "System Design": [
    "TCP Handshake",
    "Rate Limiter",
    "Database Replication",
    "Load Balancer",
    "Consistent Hashing",
    "Event-Driven Architecture",
    "Message Queue Patterns",
    "CDN Architecture",
  ],
};

interface TopicSuggestionsProps {
  onSelect: (topic: string) => void;
  selectedTopic?: string;
}

export function TopicSuggestions({
  onSelect,
  selectedTopic,
}: TopicSuggestionsProps) {
  return (
    <div className="space-y-4">
      {Object.entries(SUGGESTIONS).map(([category, topics]) => (
        <div key={category}>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
            {category}
          </h4>
          <div className="flex flex-wrap gap-2">
            {topics.map((topic) => (
              <button
                key={topic}
                type="button"
                onClick={() => onSelect(topic)}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs font-medium transition-all hover:shadow-sm",
                  selectedTopic === topic
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-background text-foreground hover:border-primary/40 hover:bg-primary/5"
                )}
              >
                {topic}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
