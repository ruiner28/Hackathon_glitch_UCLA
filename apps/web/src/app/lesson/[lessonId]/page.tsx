"use client";

import { useEffect, useState, useCallback, use } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { SceneCard } from "@/components/lesson/scene-card";
import { SceneEditor } from "@/components/lesson/scene-editor";
import {
  getLesson,
  getLessonScenes,
  updateScene,
  regenerateScene,
  regenerateSceneAssets,
  reorderScenes,
  updateLessonStyle,
  toggleSceneVeo,
  triggerRenderFinal,
} from "@/lib/api";
import { useLessonStore } from "@/hooks/useLesson";
import type { Scene, Lesson } from "@/types";
import {
  Loader2,
  Film,
  Download,
  Play,
  Monitor,
  Clapperboard,
  ChevronUp,
  ChevronDown,
  Palette,
} from "lucide-react";

export default function LessonEditorPage({
  params,
}: {
  params: Promise<{ lessonId: string }>;
}) {
  const { lessonId } = use(params);
  const router = useRouter();
  const {
    currentLesson,
    scenes,
    selectedSceneId,
    setLesson,
    setScenes,
    selectScene,
    updateScene: updateSceneInStore,
  } = useLessonStore();

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [isRegeneratingAssets, setIsRegeneratingAssets] = useState(false);
  const [isRendering, setIsRendering] = useState(false);
  const [stylePreset, setStylePreset] = useState("clean_academic");
  const [isChangingStyle, setIsChangingStyle] = useState(false);

  const selectedScene = scenes.find((s) => s.id === selectedSceneId) || null;

  useEffect(() => {
    async function load() {
      try {
        const [lesson, lessonScenes] = await Promise.all([
          getLesson(lessonId),
          getLessonScenes(lessonId),
        ]);
        setLesson(lesson as unknown as Lesson);
        setScenes(lessonScenes as unknown as Scene[]);
        setStylePreset(lesson.style_preset || "clean_academic");
        if (lessonScenes.length > 0) {
          selectScene(lessonScenes[0].id);
        }
      } catch (err) {
        console.error("Failed to load lesson:", err);
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [lessonId, setLesson, setScenes, selectScene]);

  async function handleSaveScene(updates: {
    narration_text: string;
    on_screen_text: string[];
    duration_sec?: number;
  }) {
    if (!selectedScene) return;
    setIsSaving(true);
    try {
      await updateScene(selectedScene.id, {
        ...updates,
        duration_sec: updates.duration_sec,
      });
      updateSceneInStore(selectedScene.id, {
        narration_text: updates.narration_text,
        on_screen_text_json: updates.on_screen_text,
        ...(updates.duration_sec !== undefined && { duration_sec: updates.duration_sec }),
      });
    } catch (err) {
      console.error("Failed to save scene:", err);
    } finally {
      setIsSaving(false);
    }
  }

  async function handleRegenerateScene() {
    if (!selectedScene) return;
    setIsRegenerating(true);
    try {
      await regenerateScene(selectedScene.id);
      const updatedScenes = await getLessonScenes(lessonId);
      setScenes(updatedScenes as unknown as Scene[]);
    } catch (err) {
      console.error("Failed to regenerate scene:", err);
    } finally {
      setIsRegenerating(false);
    }
  }

  async function handleRegenerateAssets() {
    if (!selectedScene) return;
    setIsRegeneratingAssets(true);
    try {
      await regenerateSceneAssets(selectedScene.id);
      const updatedScenes = await getLessonScenes(lessonId);
      setScenes(updatedScenes as unknown as Scene[]);
    } catch (err) {
      console.error("Failed to regenerate assets:", err);
    } finally {
      setIsRegeneratingAssets(false);
    }
  }

  const handleToggleVeo = useCallback(async (enabled: boolean) => {
    if (!selectedScene) return;
    try {
      await toggleSceneVeo(selectedScene.id, enabled);
      const updatedScenes = await getLessonScenes(lessonId);
      setScenes(updatedScenes as unknown as Scene[]);
    } catch (err) {
      console.error("Failed to toggle Veo:", err);
    }
  }, [selectedScene, lessonId, setScenes]);

  async function handleMoveScene(direction: "up" | "down") {
    if (!selectedScene) return;
    const idx = scenes.findIndex((s) => s.id === selectedScene.id);
    if (idx < 0) return;
    const newIdx = direction === "up" ? idx - 1 : idx + 1;
    if (newIdx < 0 || newIdx >= scenes.length) return;

    const newOrder = [...scenes];
    [newOrder[idx], newOrder[newIdx]] = [newOrder[newIdx], newOrder[idx]];
    const ids = newOrder.map((s) => s.id);

    try {
      const updated = await reorderScenes(lessonId, ids);
      setScenes(updated as unknown as Scene[]);
    } catch (err) {
      console.error("Failed to reorder:", err);
    }
  }

  async function handleStyleChange(preset: string) {
    setIsChangingStyle(true);
    try {
      await updateLessonStyle(lessonId, preset);
      setStylePreset(preset);
    } catch (err) {
      console.error("Failed to change style:", err);
    } finally {
      setIsChangingStyle(false);
    }
  }

  async function handleRenderFinal() {
    setIsRendering(true);
    try {
      await triggerRenderFinal(lessonId);
      router.push(`/lesson/${lessonId}/output`);
    } catch (err) {
      console.error("Failed to render:", err);
      setIsRendering(false);
    }
  }

  if (isLoading) {
    return (
      <>
        <Header />
        <main className="flex flex-1 items-center justify-center min-h-screen">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </main>
      </>
    );
  }

  const onScreenText = selectedScene?.on_screen_text_json || [];

  return (
    <>
      <Header />
      <main className="flex-1 flex flex-col" style={{ height: "calc(100vh - 64px)" }}>
        {/* Top Bar */}
        <div className="border-b bg-background">
          <div className="container flex h-14 items-center justify-between">
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-semibold truncate max-w-xs">
                {currentLesson?.title || "Untitled Lesson"}
              </h1>
              <div className="flex items-center gap-1.5">
                <Palette className="h-3.5 w-3.5 text-muted-foreground" />
                <select
                  value={stylePreset}
                  onChange={(e) => handleStyleChange(e.target.value)}
                  disabled={isChangingStyle}
                  className="text-xs border rounded px-2 py-1 bg-background"
                >
                  <option value="clean_academic">Clean Academic</option>
                  <option value="modern_technical">Modern Technical</option>
                  <option value="cinematic_minimal">Cinematic Minimal</option>
                </select>
              </div>
              <Badge variant="outline">{currentLesson?.status}</Badge>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => router.push(`/lesson/${lessonId}/output`)}
              >
                <Download className="mr-1.5 h-4 w-4" />
                Export
              </Button>
              <Button
                size="sm"
                onClick={handleRenderFinal}
                disabled={isRendering}
              >
                {isRendering ? (
                  <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                ) : (
                  <Film className="mr-1.5 h-4 w-4" />
                )}
                Render Final
              </Button>
            </div>
          </div>
        </div>

        {/* Three Panel Layout */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left Sidebar - Scene List */}
          <aside className="w-72 shrink-0 border-r bg-muted/30 overflow-y-auto">
            <div className="p-4">
              <h2 className="text-sm font-semibold text-muted-foreground mb-3">
                Scenes ({scenes.length})
              </h2>
              <div className="space-y-2">
                {scenes.map((scene, idx) => (
                  <div key={scene.id} className="flex items-start gap-1">
                    <div className="flex-1">
                      <SceneCard
                        scene={scene}
                        isSelected={scene.id === selectedSceneId}
                        onClick={() => selectScene(scene.id)}
                      />
                    </div>
                    {scene.id === selectedSceneId && (
                      <div className="flex flex-col gap-0.5 pt-2">
                        <button
                          onClick={() => handleMoveScene("up")}
                          disabled={idx === 0}
                          className="p-1 rounded hover:bg-muted disabled:opacity-30"
                          title="Move up"
                        >
                          <ChevronUp className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => handleMoveScene("down")}
                          disabled={idx === scenes.length - 1}
                          className="p-1 rounded hover:bg-muted disabled:opacity-30"
                          title="Move down"
                        >
                          <ChevronDown className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </aside>

          {/* Center - Preview */}
          <div className="flex-1 overflow-y-auto">
            <div className="p-6">
              <div className="aspect-video rounded-lg bg-gradient-to-br from-slate-900 to-slate-800 flex items-center justify-center mb-6 shadow-inner">
                <div className="text-center">
                  <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-white/10">
                    <Play className="h-8 w-8 text-white/80" />
                  </div>
                  <p className="text-sm text-white/60">
                    {selectedScene
                      ? `Scene ${selectedScene.scene_order + 1}: ${selectedScene.title}`
                      : "Select a scene to preview"}
                  </p>
                </div>
              </div>

              {selectedScene && (
                <div className="rounded-lg border bg-card p-4">
                  <div className="flex items-center gap-3 mb-3">
                    <Monitor className="h-5 w-5 text-muted-foreground" />
                    <h3 className="font-medium">Scene Preview</h3>
                  </div>
                  <div className="grid gap-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Render Strategy</span>
                      <span>{selectedScene.render_strategy}</span>
                    </div>
                    {!!(selectedScene.scene_spec_json?.veo_eligible) && (
                      <div className="flex justify-between items-center">
                        <span className="text-muted-foreground flex items-center gap-1">
                          <Clapperboard className="h-3.5 w-3.5" />
                          Veo Motion
                        </span>
                        <Badge variant="default" className="bg-violet-600 text-white text-[10px]">
                          Score {((selectedScene.scene_spec_json?.veo_score as number) ?? 0).toFixed(1)} — 5s clip
                        </Badge>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Status</span>
                      <Badge
                        variant={
                          selectedScene.status === "rendered"
                            ? "default"
                            : "secondary"
                        }
                      >
                        {selectedScene.status}
                      </Badge>
                    </div>
                    {onScreenText.length > 0 && (
                      <div>
                        <span className="text-muted-foreground">
                          On-Screen Text:
                        </span>
                        <ul className="mt-1 space-y-1 list-disc list-inside">
                          {onScreenText.map((text, i) => (
                            <li key={i} className="text-xs">
                              {text}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Gemini Live-ready interaction hooks */}
              {selectedScene && (
                <div className="mt-4 rounded-lg border bg-card p-4">
                  <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                    Interaction Hooks (Gemini Live-ready)
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { label: "Ask About This", icon: "💬" },
                      { label: "Explain Simpler", icon: "🎯" },
                      { label: "Show Flow Again", icon: "🔄" },
                      { label: "Deeper Dive", icon: "🔍" },
                      { label: "Quiz Me", icon: "❓" },
                    ].map((hook) => (
                      <button
                        key={hook.label}
                        className="inline-flex items-center gap-1.5 rounded-full border bg-background px-3 py-1.5 text-xs font-medium hover:bg-primary/5 hover:border-primary/30 transition-colors cursor-default"
                        title={`Future: ${hook.label} for "${selectedScene.title}"`}
                      >
                        <span>{hook.icon}</span>
                        {hook.label}
                      </button>
                    ))}
                  </div>
                  <p className="mt-2 text-[10px] text-muted-foreground/50">
                    Scene metadata exposed via /scene-interactions API for future conversational AI
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Right Panel - Scene Editor */}
          <aside className="w-96 shrink-0 border-l overflow-y-auto">
            <div className="p-4">
              {selectedScene ? (
                <SceneEditor
                  key={selectedScene.id}
                  scene={selectedScene}
                  onSave={handleSaveScene}
                  onRegenerate={handleRegenerateScene}
                  onRegenerateAssets={handleRegenerateAssets}
                  onToggleVeo={handleToggleVeo}
                  isSaving={isSaving}
                  isRegenerating={isRegenerating}
                  isRegeneratingAssets={isRegeneratingAssets}
                />
              ) : (
                <div className="flex flex-col items-center justify-center py-20 text-center text-muted-foreground">
                  <p className="text-sm">
                    Select a scene from the sidebar to edit
                  </p>
                </div>
              )}
            </div>
          </aside>
        </div>
      </main>
    </>
  );
}
