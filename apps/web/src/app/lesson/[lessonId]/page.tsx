"use client";

import { useEffect, useState, useCallback, use } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import {
  DiagramViewer,
  type ComponentClickInfo,
} from "@/components/lesson/diagram-viewer";
import { LiveChat, type ComponentQuestion } from "@/components/lesson/live-chat";
import {
  getApiBase,
  getLesson,
  getLessonScenes,
  getDiagramData,
  triggerRenderFinal,
  triggerVeoRender,
  type WalkthroughState,
} from "@/lib/api";
import { useLessonStore } from "@/hooks/useLesson";
import type { Scene, Lesson } from "@/types";
import {
  Loader2,
  Film,
  Download,
  Play,
  ChevronRight,
  Sparkles,
} from "lucide-react";

function LessonPageContent({ lessonId }: { lessonId: string }) {
  const router = useRouter();
  const { setLesson, setScenes, reset: resetLessonStore } = useLessonStore();

  const [isLoading, setIsLoading] = useState(true);
  const [lessonData, setLessonData] = useState<Lesson | null>(null);
  const [scenes, setLocalScenes] = useState<Scene[]>([]);
  const [hasDiagram, setHasDiagram] = useState(false);
  const [isRendering, setIsRendering] = useState(false);
  const [selectedSceneIdx, setSelectedSceneIdx] = useState<number | null>(null);
  const [walkthroughStates, setWalkthroughStates] = useState<WalkthroughState[]>([]);
  const [guidedStateIndex, setGuidedStateIndex] = useState(0);
  const [componentQuestion, setComponentQuestion] =
    useState<ComponentQuestion | null>(null);

  const handleComponentClick = useCallback((info: ComponentClickInfo) => {
    setComponentQuestion({
      componentId: info.componentId,
      label: info.label,
      timestamp: Date.now(),
    });
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setIsLoading(true);
      setLessonData(null);
      setLocalScenes([]);
      setHasDiagram(false);
      setWalkthroughStates([]);
      setGuidedStateIndex(0);
      setSelectedSceneIdx(null);
      resetLessonStore();
      try {
        const [lesson, lessonScenes] = await Promise.all([
          getLesson(lessonId),
          getLessonScenes(lessonId),
        ]);
        if (cancelled) return;
        const typedLesson = lesson as unknown as Lesson;
        const typedScenes = lessonScenes as unknown as Scene[];
        setLessonData(typedLesson);
        setLocalScenes(typedScenes);
        setLesson(typedLesson);
        setScenes(typedScenes);

        getDiagramData(lessonId)
          .then((d) => {
            if (cancelled) return;
            setHasDiagram(true);
            if (d.walkthrough_states?.length) {
              setWalkthroughStates(d.walkthrough_states);
            }
          })
          .catch(() => {
            if (!cancelled) setHasDiagram(false);
          });
      } catch (err) {
        console.error("Failed to load lesson:", err);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [lessonId, setLesson, setScenes, resetLessonStore]);

  const handlePrimaryVideo = useCallback(async () => {
    setIsRendering(true);
    try {
      if (hasDiagram) {
        await triggerVeoRender(lessonId);
      } else {
        await triggerRenderFinal(lessonId);
      }
      router.push(`/lesson/${lessonId}/output`);
    } catch (err) {
      console.error("Failed to generate video:", err);
      setIsRendering(false);
    }
  }, [lessonId, router, hasDiagram]);

  if (isLoading) {
    return (
      <>
        <Header />
        <main className="flex flex-1 items-center justify-center min-h-screen bg-slate-50">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">Loading lesson...</p>
          </div>
        </main>
      </>
    );
  }

  const selectedScene =
    selectedSceneIdx !== null ? scenes[selectedSceneIdx] : null;

  return (
    <>
      <Header />
      <main className="flex-1 bg-slate-50 min-h-screen">
        {/* Lesson Header */}
        <div className="border-b bg-white">
          <div className="max-w-6xl mx-auto px-6 py-5">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-primary/70 uppercase tracking-wider mb-1">
                  {lessonData?.domain?.replace(/_/g, " ") || "CS Concepts"}
                </p>
                <h1 className="text-2xl font-bold tracking-tight text-slate-900 truncate">
                  {lessonData?.title || "Untitled Lesson"}
                </h1>
                {lessonData?.summary && (
                  <p className="mt-1.5 text-sm text-slate-500 line-clamp-2 max-w-2xl">
                    {lessonData.summary}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => router.push(`/lesson/${lessonId}/output`)}
                  className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  <Download className="h-3.5 w-3.5" />
                  Export
                </button>
                <button
                  onClick={handlePrimaryVideo}
                  disabled={isRendering}
                  title={
                    hasDiagram
                      ? "Generate a multi-clip Veo animation with Lyria music"
                      : "Render slideshow video with FFmpeg"
                  }
                  className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-white hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  {isRendering ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Film className="h-3.5 w-3.5" />
                  )}
                  {hasDiagram ? "Generate Animation" : "Render Video"}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="max-w-6xl mx-auto px-6 py-6">
          {/* Interactive Diagram — Primary Experience */}
          {hasDiagram ? (
            <DiagramViewer
              lessonId={lessonId}
              className="mb-6"
              controlledStateIndex={guidedStateIndex}
              onStateChange={setGuidedStateIndex}
              onComponentClick={handleComponentClick}
              overlay={
                <LiveChat
                  lessonId={lessonId}
                  placement="diagram"
                  walkthroughStates={walkthroughStates}
                  currentWalkthroughIndex={guidedStateIndex}
                  onAdvanceState={setGuidedStateIndex}
                  componentQuestion={componentQuestion}
                />
              }
            />
          ) : (
            <div className="aspect-video rounded-xl bg-gradient-to-br from-slate-800 to-slate-900 flex items-center justify-center mb-6 shadow-lg overflow-hidden relative">
              {scenes[0]?.preview_image_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  key={`${scenes[0].id}-${scenes[0].updated_at}`}
                  src={`${getApiBase().replace(/\/$/, "")}${scenes[0].preview_image_url.startsWith("/") ? "" : "/"}${scenes[0].preview_image_url}?v=${encodeURIComponent(scenes[0].updated_at)}`}
                  alt=""
                  className="absolute inset-0 h-full w-full object-cover opacity-60"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = "none";
                  }}
                />
              ) : null}
              <div className="text-center relative z-10 px-6">
                <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-white/10 backdrop-blur">
                  <Play className="h-7 w-7 text-white/80" />
                </div>
                <p className="text-white/90 font-medium">
                  {lessonData?.title || "Lesson Preview"}
                </p>
                <p className="text-white/50 text-sm mt-1">
                  {scenes.length} scenes generated
                </p>
              </div>
            </div>
          )}

          {/* Scenes Overview */}
          {scenes.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-4">
                <Sparkles className="h-4 w-4 text-primary" />
                <h2 className="text-lg font-semibold text-slate-900">
                  Lesson Scenes
                </h2>
                <span className="text-sm text-slate-400">
                  {scenes.length} sections
                </span>
              </div>

              <div className="grid gap-3">
                {scenes.map((scene, idx) => (
                  <button
                    key={scene.id}
                    onClick={() =>
                      setSelectedSceneIdx(
                        selectedSceneIdx === idx ? null : idx,
                      )
                    }
                    className={`w-full text-left rounded-xl border bg-white p-4 transition-all hover:shadow-md ${
                      selectedSceneIdx === idx
                        ? "border-primary/30 ring-1 ring-primary/10 shadow-sm"
                        : "border-slate-200 hover:border-slate-300"
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      {/* Scene Number */}
                      <span
                        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm font-bold ${
                          selectedSceneIdx === idx
                            ? "bg-primary text-white"
                            : "bg-slate-100 text-slate-500"
                        }`}
                      >
                        {idx + 1}
                      </span>

                      {/* Scene Thumbnail */}
                      {scene.preview_image_url && (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          key={`${scene.id}-${scene.updated_at}`}
                          src={`${getApiBase().replace(/\/$/, "")}${scene.preview_image_url.startsWith("/") ? "" : "/"}${scene.preview_image_url}?v=${encodeURIComponent(scene.updated_at)}`}
                          alt=""
                          className="h-16 w-28 shrink-0 rounded-lg object-cover bg-slate-100"
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display =
                              "none";
                          }}
                        />
                      )}

                      {/* Scene Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="font-medium text-slate-900 truncate">
                            {scene.title}
                          </h3>
                          <span className="text-xs text-slate-400 shrink-0">
                            {scene.duration_sec}s
                          </span>
                        </div>
                        {scene.narration_text && (
                          <p
                            className={`mt-1 text-sm text-slate-500 leading-relaxed ${
                              selectedSceneIdx === idx
                                ? ""
                                : "line-clamp-2"
                            }`}
                          >
                            {scene.narration_text}
                          </p>
                        )}
                      </div>

                      <ChevronRight
                        className={`h-4 w-4 shrink-0 text-slate-300 transition-transform mt-2 ${
                          selectedSceneIdx === idx ? "rotate-90" : ""
                        }`}
                      />
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>
    </>
  );
}

export default function LessonPage({
  params,
}: {
  params: Promise<{ lessonId: string }>;
}) {
  const { lessonId } = use(params);
  return <LessonPageContent key={lessonId} lessonId={lessonId} />;
}
