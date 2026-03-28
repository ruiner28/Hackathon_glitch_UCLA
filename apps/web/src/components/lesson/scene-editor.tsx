"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { RefreshCw, Save, BookOpen, Clock } from "lucide-react";
import type { Scene } from "@/types";

const sceneTypeColors: Record<string, string> = {
  deterministic_animation: "bg-blue-100 text-blue-800 border-blue-200",
  generated_still_with_motion: "bg-purple-100 text-purple-800 border-purple-200",
  veo_cinematic: "bg-pink-100 text-pink-800 border-pink-200",
  code_trace: "bg-green-100 text-green-800 border-green-200",
  system_design_graph: "bg-amber-100 text-amber-800 border-amber-200",
  summary_scene: "bg-slate-100 text-slate-800 border-slate-200",
};

const sceneTypeLabels: Record<string, string> = {
  deterministic_animation: "Deterministic Animation",
  generated_still_with_motion: "Still + Motion",
  veo_cinematic: "Veo Cinematic",
  code_trace: "Code Trace",
  system_design_graph: "System Design Graph",
  summary_scene: "Summary",
};

interface SceneEditorProps {
  scene: Scene;
  onSave: (updates: {
    narration_text: string;
    on_screen_text: string[];
  }) => void;
  onRegenerate: () => void;
  isSaving?: boolean;
  isRegenerating?: boolean;
}

export function SceneEditor({
  scene,
  onSave,
  onRegenerate,
  isSaving = false,
  isRegenerating = false,
}: SceneEditorProps) {
  const narrationText = scene.narration_text || "";
  const onScreenTextArr = scene.on_screen_text_json || [];

  const [narration, setNarration] = useState(narrationText);
  const [onScreenText, setOnScreenText] = useState(onScreenTextArr.join("\n"));

  const colorClass =
    sceneTypeColors[scene.scene_type] ||
    "bg-gray-100 text-gray-800 border-gray-200";

  const hasChanges =
    narration !== narrationText ||
    onScreenText !== onScreenTextArr.join("\n");

  function handleSave() {
    onSave({
      narration_text: narration,
      on_screen_text: onScreenText
        .split("\n")
        .map((t) => t.trim())
        .filter(Boolean),
    });
  }

  const sourceRefs = scene.source_refs_json || [];

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h3 className="text-lg font-semibold">{scene.title}</h3>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span
            className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${colorClass}`}
          >
            {sceneTypeLabels[scene.scene_type] || scene.scene_type}
          </span>
          <Badge variant="outline" className="text-xs">
            {scene.render_strategy}
          </Badge>
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <Clock className="h-3 w-3" />
            {scene.duration_sec}s
          </span>
        </div>
      </div>

      <Separator />

      <div className="space-y-2">
        <Label htmlFor="narration">Narration Text</Label>
        <Textarea
          id="narration"
          value={narration}
          onChange={(e) => setNarration(e.target.value)}
          rows={6}
          className="resize-y"
          placeholder="Enter narration text..."
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="onscreen">On-Screen Text (one per line)</Label>
        <Textarea
          id="onscreen"
          value={onScreenText}
          onChange={(e) => setOnScreenText(e.target.value)}
          rows={4}
          className="resize-y"
          placeholder="Key points shown on screen..."
        />
      </div>

      {sourceRefs.length > 0 && (
        <div className="space-y-2">
          <Label className="flex items-center gap-1.5">
            <BookOpen className="h-3.5 w-3.5" />
            Source References
          </Label>
          <ul className="space-y-1">
            {sourceRefs.map((ref, i) => (
              <li
                key={i}
                className="text-xs text-muted-foreground bg-muted rounded px-2 py-1"
              >
                {ref}
              </li>
            ))}
          </ul>
        </div>
      )}

      <Separator />

      <div className="flex items-center gap-2">
        <Button
          onClick={handleSave}
          disabled={!hasChanges || isSaving}
          size="sm"
        >
          <Save className="mr-1.5 h-4 w-4" />
          {isSaving ? "Saving..." : "Save Changes"}
        </Button>
        <Button
          onClick={onRegenerate}
          disabled={isRegenerating}
          variant="outline"
          size="sm"
        >
          <RefreshCw
            className={`mr-1.5 h-4 w-4 ${isRegenerating ? "animate-spin" : ""}`}
          />
          {isRegenerating ? "Regenerating..." : "Regenerate"}
        </Button>
      </div>
    </div>
  );
}
