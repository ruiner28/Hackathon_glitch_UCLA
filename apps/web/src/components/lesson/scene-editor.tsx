"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
  RefreshCw,
  Save,
  BookOpen,
  Clock,
  ImageIcon,
  Clapperboard,
  Loader2,
} from "lucide-react";
import { sceneRenderMode, sceneWillUseVeo } from "@/lib/scene-spec";
import type { Scene, SceneRenderMode } from "@/types";

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
    duration_sec?: number;
  }) => void;
  onRegenerate: () => void;
  onRegenerateAssets?: () => void;
  onRenderModeChange?: (mode: SceneRenderMode) => void;
  isSaving?: boolean;
  isRegenerating?: boolean;
  isRegeneratingAssets?: boolean;
}

export function SceneEditor({
  scene,
  onSave,
  onRegenerate,
  onRegenerateAssets,
  onRenderModeChange,
  isSaving = false,
  isRegenerating = false,
  isRegeneratingAssets = false,
}: SceneEditorProps) {
  const narrationText = scene.narration_text || "";
  const onScreenTextArr = scene.on_screen_text_json || [];

  const [narration, setNarration] = useState(narrationText);
  const [onScreenText, setOnScreenText] = useState(onScreenTextArr.join("\n"));
  const [duration, setDuration] = useState(scene.duration_sec);

  const colorClass =
    sceneTypeColors[scene.scene_type] ||
    "bg-gray-100 text-gray-800 border-gray-200";

  const renderMode = sceneRenderMode(scene);
  const willVeo = sceneWillUseVeo(scene);
  const stylePreset = String(scene.scene_spec_json?.style_preset || "").trim();
  const continuityAnchor = String(
    scene.scene_spec_json?.continuity_anchor || ""
  ).trim();
  const transitionNote = String(
    scene.scene_spec_json?.transition_note || ""
  ).trim();

  const hasChanges =
    narration !== narrationText ||
    onScreenText !== onScreenTextArr.join("\n") ||
    duration !== scene.duration_sec;

  function handleSave() {
    onSave({
      narration_text: narration,
      on_screen_text: onScreenText
        .split("\n")
        .map((t) => t.trim())
        .filter(Boolean),
      duration_sec: duration !== scene.duration_sec ? duration : undefined,
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
          {stylePreset && (
            <Badge variant="secondary" className="text-xs">
              Style: {stylePreset}
            </Badge>
          )}
          <Badge
            variant="outline"
            className={
              willVeo
                ? "text-xs border-violet-300 text-violet-700"
                : "text-xs"
            }
          >
            {willVeo ? "Veo-capable" : "Static frame"}
          </Badge>
        </div>
      </div>

      <Separator />

      {/* Duration control */}
      <div className="space-y-1.5">
        <Label htmlFor="duration" className="flex items-center gap-1.5">
          <Clock className="h-3.5 w-3.5" />
          Duration (seconds)
        </Label>
        <Input
          id="duration"
          type="number"
          min={3}
          max={120}
          value={duration}
          onChange={(e) => setDuration(Number(e.target.value))}
          className="w-32"
        />
      </div>

      {/* Motion: Auto / Static / Veo — maps to scene_spec_json.render_mode */}
      {onRenderModeChange && (
        <div className="rounded-lg border p-3 bg-card space-y-2">
          <div className="flex items-center gap-2">
            <Clapperboard className="h-4 w-4 text-violet-500" />
            <div>
              <p className="text-sm font-medium">Motion (GenMedia)</p>
              <p className="text-xs text-muted-foreground">
                Auto uses eligibility; Static skips Veo; Veo forces a 3–5s clip when the provider allows.
              </p>
            </div>
          </div>
          <select
            className="w-full text-sm border rounded-md px-2 py-1.5 bg-background"
            value={renderMode}
            onChange={(e) =>
              onRenderModeChange(e.target.value as SceneRenderMode)
            }
          >
            <option value="auto">Auto (score + policy)</option>
            <option value="force_static">Force static image</option>
            <option value="force_veo">Force Veo clip</option>
          </select>
        </div>
      )}

      {(continuityAnchor || transitionNote) && (
        <div className="rounded-lg border border-dashed p-3 bg-muted/20 space-y-1.5">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Continuity
          </p>
          {continuityAnchor && (
            <p className="text-xs">
              <span className="text-muted-foreground">Anchor: </span>
              {continuityAnchor}
            </p>
          )}
          {transitionNote && (
            <p className="text-xs">
              <span className="text-muted-foreground">Bridge: </span>
              {transitionNote}
            </p>
          )}
        </div>
      )}

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
                key={`ref-${scene.id}-${i}`}
                className="text-xs text-muted-foreground bg-muted rounded px-2 py-1"
              >
                {ref}
              </li>
            ))}
          </ul>
        </div>
      )}

      <Separator />

      {/* Action Buttons */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Button
            onClick={handleSave}
            disabled={!hasChanges || isSaving}
            size="sm"
          >
            {isSaving ? (
              <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-1.5 h-4 w-4" />
            )}
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
            {isRegenerating ? "Regenerating..." : "Regenerate Scene"}
          </Button>
        </div>
        {onRegenerateAssets && (
          <Button
            onClick={onRegenerateAssets}
            disabled={isRegeneratingAssets}
            variant="outline"
            size="sm"
            className="w-full"
          >
            {isRegeneratingAssets ? (
              <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
            ) : (
              <ImageIcon className="mr-1.5 h-4 w-4" />
            )}
            {isRegeneratingAssets ? "Regenerating Assets..." : "Regenerate Image & Audio"}
          </Button>
        )}
      </div>
    </div>
  );
}
