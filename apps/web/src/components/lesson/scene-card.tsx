"use client";

import { cn } from "@/lib/utils";
import { getApiBase } from "@/lib/api";
import { sceneWillUseVeo } from "@/lib/scene-spec";
import { Clock, Clapperboard, ImageIcon } from "lucide-react";
import type { Scene } from "@/types";

const sceneTypeColors: Record<string, string> = {
  deterministic_animation: "bg-blue-100 text-blue-800",
  generated_still_with_motion: "bg-purple-100 text-purple-800",
  veo_cinematic: "bg-pink-100 text-pink-800",
  code_trace: "bg-green-100 text-green-800",
  system_design_graph: "bg-amber-100 text-amber-800",
  summary_scene: "bg-slate-100 text-slate-800",
  primary_visual_walkthrough: "bg-teal-100 text-teal-800",
};

const sceneTypeLabels: Record<string, string> = {
  deterministic_animation: "Animation",
  generated_still_with_motion: "Still + Motion",
  veo_cinematic: "Cinematic",
  code_trace: "Code Trace",
  system_design_graph: "System Design",
  summary_scene: "Summary",
  primary_visual_walkthrough: "Walkthrough",
};

interface SceneCardProps {
  scene: Scene;
  isSelected: boolean;
  onClick: () => void;
}

const STYLE_LABELS: Record<string, string> = {
  clean_academic: "Academic",
  modern_technical: "Technical",
  cinematic_minimal: "Cinematic",
};

export function SceneCard({ scene, isSelected, onClick }: SceneCardProps) {
  const colorClass =
    sceneTypeColors[scene.scene_type] || "bg-gray-100 text-gray-800";

  const sp = scene.scene_spec_json?.style_preset;
  const styleKey = typeof sp === "string" ? sp : "";
  const styleShort = styleKey
    ? STYLE_LABELS[styleKey] || styleKey
    : null;
  const thumb =
    scene.preview_image_url &&
    `${getApiBase().replace(/\/$/, "")}${scene.preview_image_url.startsWith("/") ? "" : "/"}${scene.preview_image_url}?v=${encodeURIComponent(scene.updated_at)}`;
  const useVeo = sceneWillUseVeo(scene);

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
      <div className="flex gap-2">
        {thumb ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={thumb}
            alt=""
            className="h-14 w-24 shrink-0 rounded object-cover bg-muted"
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
        ) : (
          <div className="flex h-14 w-24 shrink-0 items-center justify-center rounded bg-muted text-muted-foreground">
            <ImageIcon className="h-5 w-5" />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-bold">
                {scene.scene_order + 1}
              </span>
              <span className="text-sm font-medium line-clamp-2">
                {scene.title}
              </span>
            </div>
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <span
              className={cn(
                "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                colorClass
              )}
            >
              {sceneTypeLabels[scene.scene_type] || scene.scene_type}
            </span>
            {styleShort && (
              <span className="inline-flex rounded-full bg-slate-100 text-slate-700 px-1.5 py-0.5 text-[10px] font-medium">
                {styleShort}
              </span>
            )}
            <span
              className={cn(
                "inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[10px] font-medium",
                useVeo
                  ? "bg-violet-100 text-violet-700"
                  : "bg-stone-100 text-stone-600"
              )}
            >
              {useVeo ? (
                <>
                  <Clapperboard className="h-2.5 w-2.5" />
                  Veo
                </>
              ) : (
                <>
                  <ImageIcon className="h-2.5 w-2.5" />
                  Static
                </>
              )}
            </span>
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <Clock className="h-3 w-3" />
              {scene.duration_sec}s
            </span>
          </div>
        </div>
      </div>

      {scene.narration_text && (
        <p className="mt-2 text-xs text-muted-foreground line-clamp-2">
          {scene.narration_text}
        </p>
      )}
    </button>
  );
}
