"use client";

import { useEffect, useCallback, useRef, use } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { ProcessingSteps } from "@/components/lesson/processing-steps";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  getLesson,
  triggerExtract,
  triggerPlan,
  triggerGenerateDiagram,
  triggerCompileScenes,
  triggerGenerateAssets,
  triggerRenderPreview,
} from "@/lib/api";
import {
  useLessonStore,
  mapLessonStatusToProcessing,
} from "@/hooks/useLesson";
import { Loader2, ArrowRight, AlertCircle, CheckCircle2 } from "lucide-react";

export default function ProcessingPage({
  params,
}: {
  params: Promise<{ lessonId: string }>;
}) {
  const { lessonId } = use(params);
  const router = useRouter();
  const { processingStatus, setProcessingStatus, setLesson } =
    useLessonStore();
  const pipelineStarted = useRef(false);

  const completedSteps = Object.values(processingStatus.steps).filter(
    (s) => s === "complete"
  ).length;
  const totalSteps = Object.keys(processingStatus.steps).length;
  const progressPercent = (completedSteps / totalSteps) * 100;
  const hasError = Object.values(processingStatus.steps).some(
    (s) => s === "error"
  );
  const isComplete = completedSteps === totalSteps;

  const runPipeline = useCallback(async () => {
    if (pipelineStarted.current) return;
    pipelineStarted.current = true;

    const steps = [
      {
        fn: () => triggerExtract(lessonId),
        status: "extracting",
        message: "Extracting concepts from source material...",
      },
      {
        fn: () => triggerPlan(lessonId),
        status: "planning",
        message: "Creating pedagogical lesson plan...",
      },
      {
        fn: () => triggerGenerateDiagram(lessonId).catch(() => null),
        status: "diagram_generation",
        message: "Generating architecture diagram...",
      },
      {
        fn: () => triggerCompileScenes(lessonId),
        status: "compiling",
        message: "Compiling scene specifications...",
      },
      {
        fn: () => triggerGenerateAssets(lessonId),
        status: "generating_assets",
        message: "Generating visuals and narration...",
      },
      {
        fn: () => triggerRenderPreview(lessonId),
        status: "rendering",
        message: "Rendering preview...",
      },
    ];

    for (const step of steps) {
      setProcessingStatus(mapLessonStatusToProcessing(step.status));
      try {
        await step.fn();
      } catch (err) {
        console.error(`Pipeline step ${step.status} failed:`, err);
        setProcessingStatus(mapLessonStatusToProcessing("error"));
        return;
      }
    }

    setProcessingStatus(mapLessonStatusToProcessing("completed"));

    try {
      const lesson = await getLesson(lessonId);
      setLesson(lesson as any);
    } catch {}

    setTimeout(() => router.push(`/lesson/${lessonId}`), 1500);
  }, [lessonId, setProcessingStatus, setLesson, router]);

  useEffect(() => {
    runPipeline();
  }, [runPipeline]);

  return (
    <>
      <Header />
      <main className="min-h-screen flex-1 bg-[hsl(var(--page-bg))]">
        <div className="mx-auto max-w-md px-6 py-16 sm:py-20">
          <div className="mb-8 text-center">
            <p className="section-label mb-4">Pipeline</p>
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-slate-200/90 bg-white shadow-sm ring-1 ring-slate-900/[0.04]">
              {isComplete ? (
                <CheckCircle2 className="h-8 w-8 text-emerald-600" />
              ) : hasError ? (
                <AlertCircle className="h-8 w-8 text-destructive" />
              ) : (
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              )}
            </div>
            <h1 className="text-xl font-semibold tracking-tight text-slate-900">
              {isComplete
                ? "Ready!"
                : hasError
                  ? "Something went wrong"
                  : "Building your lesson"}
            </h1>
            <p className="mt-2 text-sm text-slate-600">
              {processingStatus.message}
            </p>
          </div>

          <Card className="border-slate-200/90 shadow-sm ring-1 ring-slate-900/[0.03]">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium text-slate-700">
                  Progress
                </CardTitle>
                <span className="text-xs font-medium text-slate-400">
                  {completedSteps}/{totalSteps}
                </span>
              </div>
              <Progress value={progressPercent} className="mt-2 h-1.5" />
            </CardHeader>
            <CardContent>
              <ProcessingSteps
                steps={processingStatus.steps}
                message={processingStatus.message}
              />
            </CardContent>
          </Card>

          {isComplete && (
            <div className="mt-6 text-center">
              <Button
                size="lg"
                onClick={() => router.push(`/lesson/${lessonId}`)}
              >
                Open Lesson
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          )}

          {hasError && (
            <div className="mt-6 text-center space-y-3">
              <p className="text-sm text-slate-400">
                You can retry or view partial results.
              </p>
              <div className="flex items-center justify-center gap-3">
                <Button
                  variant="outline"
                  onClick={() => {
                    pipelineStarted.current = false;
                    runPipeline();
                  }}
                >
                  Retry
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => router.push(`/lesson/${lessonId}`)}
                >
                  View Partial
                </Button>
              </div>
            </div>
          )}
        </div>
      </main>
    </>
  );
}
