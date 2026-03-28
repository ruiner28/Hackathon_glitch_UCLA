"use client";

import { cn } from "@/lib/utils";
import { Clock } from "lucide-react";
import type { Scene } from "@/types";

const sceneTypeColors: Record<string, string> = {
  deterministic_animation: "bg-blue-100 text-blue-800",
  generated_still_with_motion: "bg-purple-100 text-purple-800",
  veo_cinematic: "bg-pink-100 text-pink-800",
  code_trace: "bg-green-100 text-green-800",
  system_design_graph: "bg-amber-100 text-amber-800",
  summary_scene: "bg-slate-100 text-slate-800",
};

const sceneTypeLabels: Record<string, string> = {
  deterministic_animation: "Animation",
  generated_still_with_motion: "Still + Motion",
  veo_cinematic: "Cinematic",
  code_trace: "Code Trace",
  system_design_graph: "System Design",
  summary_scene: "Summary",
};

interface SceneCardProps {
  scene: Scene;
  isSelected: boolean;
  onClick: () => void;
}

export function SceneCard({ scene, isSelected, onClick }: SceneCardProps) {
  const colorClass =
    sceneTypeColors[scene.scene_type] || "bg-gray-100 text-gray-800";

  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full text-left rounded-lg border p-3 transition-all hover:shadow-md",
        isSelected
          ? "border-primary bg-primary/5 ring-2 ring-primary/20"
          : "border-border hover:border-primary/30"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-bold">
            {scene.scene_order + 1}
          </span>
          <span className="text-sm font-medium line-clamp-1">
            {scene.title}
          </span>
        </div>
      </div>

      <div className="mt-2 flex items-center gap-2">
        <span
          className={cn(
            "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
            colorClass
          )}
        >
          {sceneTypeLabels[scene.scene_type] || scene.scene_type}
        </span>
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          <Clock className="h-3 w-3" />
          {scene.duration_sec}s
        </span>
      </div>

      {scene.narration_text && (
        <p className="mt-2 text-xs text-muted-foreground line-clamp-2">
          {scene.narration_text}
        </p>
      )}
    </button>
  );
}
