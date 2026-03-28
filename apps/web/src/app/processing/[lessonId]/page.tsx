"use client";

import { useEffect, useCallback, useRef, use } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
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
        message: "Generating primary architecture diagram...",
      },
      {
        fn: () => triggerCompileScenes(lessonId),
        status: "compiling",
        message: "Compiling scene specifications...",
      },
      {
        fn: () => triggerGenerateAssets(lessonId),
        status: "generating_assets",
        message: "Generating narration and visual assets...",
      },
      {
        fn: () => triggerRenderPreview(lessonId),
        status: "rendering",
        message: "Rendering video preview...",
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
      <main className="flex-1 gradient-bg">
        <div className="container py-16">
          <div className="mx-auto max-w-lg">
            <div className="mb-8 text-center">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                {isComplete ? (
                  <CheckCircle2 className="h-8 w-8 text-green-600" />
                ) : hasError ? (
                  <AlertCircle className="h-8 w-8 text-destructive" />
                ) : (
                  <Loader2 className="h-8 w-8 animate-spin text-primary" />
                )}
              </div>
              <h1 className="text-2xl font-bold">
                {isComplete
                  ? "Lesson Ready!"
                  : hasError
                  ? "Processing Error"
                  : "Building Your Lesson"}
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                {processingStatus.message}
              </p>
            </div>

            <Card className="shadow-lg">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">Progress</CardTitle>
                  <span className="text-sm font-medium text-muted-foreground">
                    {completedSteps}/{totalSteps}
                  </span>
                </div>
                <Progress value={progressPercent} className="mt-2 h-2" />
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
                  View Lesson
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </div>
            )}

            {hasError && (
              <div className="mt-6 text-center space-y-3">
                <p className="text-sm text-muted-foreground">
                  Something went wrong. You can retry the pipeline or view
                  partial results.
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
        </div>
      </main>
      <Footer />
    </>
  );
}
