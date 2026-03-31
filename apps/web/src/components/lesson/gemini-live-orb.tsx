"use client";

import { cn } from "@/lib/utils";

/** Swap to a Veo texture (e.g. webp) by changing this path in one place. */
export const GEMINI_ORB_TEXTURE_SRC = "/assets/gemini-live-orb.svg";

export type LiveOrbVisualState =
  | "idle"
  | "connecting"
  | "listening"
  | "thinking"
  | "speaking";

interface GeminiLiveOrbProps {
  state: LiveOrbVisualState;
  className?: string;
  /** Pixel size of the orb image (default 52) */
  size?: number;
  /** Optional override for texture (e.g. Veo still). */
  textureSrc?: string;
}

/**
 * Gemini Live orb — SVG texture, animated rings, state-driven motion (listen / think / speak).
 */
export function GeminiLiveOrb({
  state,
  className,
  size = 52,
  textureSrc = GEMINI_ORB_TEXTURE_SRC,
}: GeminiLiveOrbProps) {
  const s = size;
  const outer = s + 18;

  return (
    <div
      className={cn("relative flex shrink-0 items-center justify-center", className)}
      style={{ width: outer, height: outer }}
      aria-hidden
    >
      <div
        className={cn(
          "pointer-events-none absolute rounded-full border-2 opacity-90 transition-all duration-500",
          state === "idle" && "border-violet-400/35 scale-100",
          state === "connecting" &&
            "border-amber-400/80 scale-110 animate-orb-ring-spin-fast",
          state === "listening" &&
            "border-emerald-400/70 scale-[1.12] animate-orb-ring-spin",
          state === "thinking" &&
            "border-amber-300/75 scale-[1.08] animate-orb-ring-spin",
          state === "speaking" &&
            "border-fuchsia-400/80 scale-[1.1] animate-orb-ring-spin",
        )}
        style={{ width: outer, height: outer }}
      />
      <div
        className={cn(
          "pointer-events-none absolute rounded-full border opacity-45",
          state === "listening" && "border-emerald-300/50 scale-125",
          state === "speaking" && "border-fuchsia-300/55 scale-115",
          state === "thinking" && "border-amber-200/40 scale-110",
        )}
        style={{ width: outer + 16, height: outer + 16 }}
      />

      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={textureSrc}
        alt=""
        width={s}
        height={s}
        className={cn(
          "relative z-[1] rounded-full object-cover shadow-lg ring-1 ring-white/20",
          state === "idle" && "animate-orb-breathe",
          state === "listening" && "animate-orb-listen",
          state === "thinking" && "animate-orb-wobble",
          state === "speaking" && "animate-orb-speak",
          state === "connecting" && "animate-pulse opacity-95",
        )}
        draggable={false}
      />
    </div>
  );
}

export function mapToOrbState(
  connection: "idle" | "connecting" | "connected" | "error",
  speaking: "idle" | "listening" | "thinking" | "speaking",
): LiveOrbVisualState {
  if (connection === "connecting") return "connecting";
  if (connection !== "connected") return "idle";
  if (speaking === "listening") return "listening";
  if (speaking === "thinking") return "thinking";
  if (speaking === "speaking") return "speaking";
  return "idle";
}
