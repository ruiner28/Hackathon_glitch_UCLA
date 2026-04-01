"use client";

import { useEffect, useState, useRef, useCallback, use } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { QuizDisplay } from "@/components/lesson/quiz-display";
import {
  getLesson,
  getTranscript,
  getQuiz,
  getEvaluation,
  triggerEvaluate,
  downloadLesson,
  getVideoUrl,
  getSubtitlesUrl,
  checkVideoReady,
} from "@/lib/api";
import {
  Download,
  FileText,
  HelpCircle,
  Lightbulb,
  Play,
  Loader2,
  ArrowLeft,
  Clock,
  CheckCircle2,
  Film,
  BookOpen,
  Target,
  AlertTriangle,
  Subtitles,
  ShieldCheck,
  BarChart3,
  RefreshCw,
} from "lucide-react";

const SCENE_TYPE_LABELS: Record<string, string> = {
  deterministic_animation: "Concept Flow",
  generated_still_with_motion: "Visual",
  veo_cinematic: "Cinematic",
  code_trace: "Code Trace",
  system_design_graph: "Architecture",
  summary_scene: "Summary",
};

interface TranscriptScene {
  scene_id: string;
  scene_order: number;
  title: string;
  text: string;
  timestamp: number;
  duration_sec: number;
  scene_type: string;
  learning_objective: string;
  teaching_note: string;
}

interface TranscriptData {
  full_text: string;
  total_duration_sec: number;
  scenes: TranscriptScene[];
  misconceptions: string[];
  prerequisites: string[];
}

interface QuizData {
  questions: Array<{
    question: string;
    options: string[];
    correct_index: number;
    explanation: string;
  }>;
}

interface EvalScoreCategory {
  score: number;
  feedback: string;
}

interface EvalSceneScore {
  scene_index: number;
  title: string;
  score: number;
  flags: string[];
  confidence: string;
}

interface EvalData {
  overall_score: number;
  grade: string;
  deterministic_score: number;
  llm_score: number;
  content_accuracy: EvalScoreCategory;
  pedagogical_quality: EvalScoreCategory;
  visual_quality: EvalScoreCategory;
  narration_quality: EvalScoreCategory;
  engagement: EvalScoreCategory;
  flags: string[];
  detailed_flags: Array<{
    severity: string;
    category: string;
    message: string;
    scene_index?: number;
  }>;
  scene_scores: EvalSceneScore[];
  suggestions: string[];
  scene_count: number;
  total_duration_sec: number;
  summary: { errors: number; warnings: number; info: number };
}

export default function OutputPage({
  params,
}: {
  params: Promise<{ lessonId: string }>;
}) {
  const { lessonId } = use(params);
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(true);
  const [lessonTitle, setLessonTitle] = useState("");
  const [lessonSummary, setLessonSummary] = useState("");
  const [lessonDomain, setLessonDomain] = useState("");
  const [transcript, setTranscript] = useState<TranscriptData | null>(null);
  const [quiz, setQuiz] = useState<QuizData | null>(null);
  const [downloadStatus, setDownloadStatus] = useState<string | null>(null);
  const [videoReady, setVideoReady] = useState(false);
  const [showSubtitles, setShowSubtitles] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [videoDuration, setVideoDuration] = useState(0);
  const [activeSceneIdx, setActiveSceneIdx] = useState(-1);
  const [evaluation, setEvaluation] = useState<EvalData | null>(null);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    async function load() {
      try {
        const [lesson, transcriptData, quizData, hasVideo, evalData] = await Promise.all([
          getLesson(lessonId),
          getTranscript(lessonId).catch(() => null),
          getQuiz(lessonId).catch(() => null),
          checkVideoReady(lessonId),
          getEvaluation(lessonId).catch(() => null),
        ]);

        setLessonTitle(lesson.title);
        setLessonSummary(lesson.summary || "");
        setLessonDomain(lesson.domain);
        setTranscript(transcriptData);
        setQuiz(quizData);
        setVideoReady(hasVideo);
        if (evalData?.report_json) {
          setEvaluation(evalData.report_json as unknown as EvalData);
        }
      } catch (err) {
        console.error("Failed to load output:", err);
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [lessonId]);

  async function handleRunEvaluation() {
    setIsEvaluating(true);
    try {
      const result = await triggerEvaluate(lessonId);
      if (result?.report_json) {
        setEvaluation(result.report_json as unknown as EvalData);
      }
    } catch (err) {
      console.error("Evaluation failed:", err);
    } finally {
      setIsEvaluating(false);
    }
  }

  const handleTimeUpdate = useCallback(() => {
    if (!videoRef.current) return;
    const t = videoRef.current.currentTime;
    setCurrentTime(t);
    if (transcript?.scenes) {
      let idx = -1;
      for (let i = 0; i < transcript.scenes.length; i++) {
        if (t >= transcript.scenes[i].timestamp) idx = i;
      }
      setActiveSceneIdx(idx);
    }
  }, [transcript]);

  const seekToScene = useCallback((timestamp: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = timestamp;
      videoRef.current.play().catch(() => {});
    }
  }, []);

  async function handleDownload() {
    setDownloadStatus("loading");
    try {
      await downloadLesson(lessonId);
      setDownloadStatus("done");
      setTimeout(() => setDownloadStatus(null), 3000);
    } catch (err) {
      console.error("Download failed:", err);
      setDownloadStatus("error");
      setTimeout(() => setDownloadStatus(null), 3000);
    }
  }

  if (isLoading) {
    return (
      <>
        <Header />
        <main className="flex min-h-screen flex-1 flex-col items-center justify-center gap-3 bg-[hsl(var(--page-bg))]">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm text-slate-500">Loading export…</p>
        </main>
      </>
    );
  }

  const sceneCount = transcript?.scenes.length || 0;
  const totalDuration = transcript?.total_duration_sec || 0;

  return (
    <>
      <Header />
      <main className="flex-1 bg-[hsl(var(--page-bg))] pb-16">
        <div className="container py-8 sm:py-10">
          <div className="mx-auto max-w-5xl px-1 sm:px-0">
            <Button
              variant="ghost"
              size="sm"
              className="-ml-1 mb-6 text-slate-600 hover:text-slate-900"
              onClick={() => router.push(`/lesson/${lessonId}`)}
            >
              <ArrowLeft className="mr-1.5 h-4 w-4" />
              Back to Editor
            </Button>

            {/* Lesson Header */}
            <div className="mb-8">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <Badge
                    variant="outline"
                    className="mb-3 border-slate-200 capitalize text-xs font-medium text-slate-600"
                  >
                    {lessonDomain.replace(/_/g, " ")}
                  </Badge>
                  <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
                    {lessonTitle}
                  </h1>
                  {lessonSummary && (
                    <p className="mt-2 max-w-2xl leading-relaxed text-slate-600">
                      {lessonSummary}
                    </p>
                  )}
                </div>
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-slate-500">
                <span className="flex items-center gap-1.5">
                  <Film className="h-4 w-4 text-primary/70" />
                  {sceneCount} scenes
                </span>
                <span className="flex items-center gap-1.5">
                  <Clock className="h-4 w-4 text-primary/70" />
                  {formatDuration(totalDuration)}
                </span>
                {quiz && (
                  <span className="flex items-center gap-1.5">
                    <HelpCircle className="h-4 w-4 text-primary/70" />
                    {quiz.questions.length} quiz questions
                  </span>
                )}
              </div>
            </div>

            {/* Video Player */}
            <div className="mb-6">
              {videoReady ? (
                <div>
                  <div className="aspect-video rounded-t-xl overflow-hidden shadow-2xl border border-border/50 bg-black ring-1 ring-black/5">
                    <video
                      ref={videoRef}
                      className="w-full h-full"
                      controls
                      preload="metadata"
                      onTimeUpdate={handleTimeUpdate}
                      onLoadedMetadata={() => {
                        if (videoRef.current) setVideoDuration(videoRef.current.duration);
                      }}
                      crossOrigin="anonymous"
                    >
                      <source src={getVideoUrl(lessonId)} type="video/mp4" />
                      {showSubtitles && (
                        <track
                          kind="subtitles"
                          src={getSubtitlesUrl(lessonId)}
                          srcLang="en"
                          label="English"
                          default
                        />
                      )}
                    </video>
                  </div>

                  {/* Scene Timeline Bar */}
                  {transcript && transcript.scenes.length > 0 && videoDuration > 0 && (
                    <div className="bg-card border border-t-0 border-border/50 rounded-b-xl px-4 py-3">
                      <div className="flex items-center gap-3 mb-2">
                        <span className="text-xs text-muted-foreground font-medium">
                          Scene Timeline
                        </span>
                        <span className="text-xs text-muted-foreground/60 tabular-nums ml-auto">
                          {formatTime(currentTime)} / {formatTime(videoDuration)}
                        </span>
                      </div>
                      <div className="flex gap-[2px] h-8 rounded overflow-hidden">
                        {transcript.scenes.map((scene, i) => {
                          const width = (scene.duration_sec / totalDuration) * 100;
                          const isActive = i === activeSceneIdx;
                          return (
                            <button
                              key={scene.scene_id}
                              className={`relative h-full transition-all cursor-pointer group ${
                                isActive
                                  ? "bg-primary ring-1 ring-primary shadow-sm"
                                  : "bg-muted hover:bg-muted-foreground/20"
                              }`}
                              style={{ width: `${Math.max(width, 2)}%` }}
                              onClick={() => seekToScene(scene.timestamp)}
                              title={`${scene.title} (${formatTime(scene.timestamp)})`}
                            >
                              <span className={`absolute inset-x-0 bottom-0 text-[9px] truncate px-0.5 text-center font-medium ${
                                isActive ? "text-primary-foreground" : "text-muted-foreground/60 group-hover:text-foreground/70"
                              }`}>
                                {i + 1}
                              </span>
                            </button>
                          );
                        })}
                      </div>
                      {activeSceneIdx >= 0 && transcript.scenes[activeSceneIdx] && (
                        <p className="text-xs text-muted-foreground mt-1.5 truncate">
                          <span className="font-medium text-foreground/80">
                            {transcript.scenes[activeSceneIdx].title}
                          </span>
                          {transcript.scenes[activeSceneIdx].learning_objective && (
                            <span className="ml-2 text-muted-foreground/60">
                              — {transcript.scenes[activeSceneIdx].learning_objective}
                            </span>
                          )}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <div className="aspect-video rounded-xl bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center shadow-2xl border border-slate-700/50 overflow-hidden relative">
                  <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_rgba(59,130,246,0.08),transparent_70%)]" />
                  <div className="text-center relative z-10">
                    <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-white/5 border border-white/10">
                      <Play className="h-10 w-10 text-white/50" />
                    </div>
                    <p className="text-base font-medium text-white/70">
                      Video Not Yet Generated
                    </p>
                    <p className="mt-1 text-sm text-white/40 max-w-sm">
                      From the lesson page, use &quot;Generate Animation&quot;
                      (diagram lessons) or &quot;Render Video&quot; to create the
                      MP4.
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <div className="mb-8 flex items-center gap-3">
              <Button
                onClick={handleDownload}
                disabled={downloadStatus === "loading" || !videoReady}
                size="lg"
              >
                {downloadStatus === "loading" ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : downloadStatus === "done" ? (
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                ) : (
                  <Download className="mr-2 h-4 w-4" />
                )}
                {downloadStatus === "done"
                  ? "Downloaded!"
                  : downloadStatus === "error"
                  ? "Download Failed"
                  : "Download MP4"}
              </Button>
              <Button
                variant={showSubtitles ? "default" : "outline"}
                size="lg"
                onClick={() => setShowSubtitles(!showSubtitles)}
                disabled={!videoReady}
              >
                <Subtitles className="mr-2 h-4 w-4" />
                {showSubtitles ? "Subtitles On" : "Subtitles Off"}
              </Button>
              <Button
                variant="outline"
                size="lg"
                onClick={() => router.push(`/lesson/${lessonId}`)}
              >
                <BookOpen className="mr-2 h-4 w-4" />
                Edit Scenes
              </Button>
            </div>

            {/* Tabs */}
            <Tabs defaultValue="transcript" className="w-full">
              <TabsList className="grid w-full grid-cols-5">
                <TabsTrigger value="transcript" className="gap-1.5">
                  <FileText className="h-4 w-4" />
                  Transcript
                </TabsTrigger>
                <TabsTrigger value="quiz" className="gap-1.5">
                  <HelpCircle className="h-4 w-4" />
                  Quiz
                </TabsTrigger>
                <TabsTrigger value="takeaways" className="gap-1.5">
                  <Lightbulb className="h-4 w-4" />
                  Takeaways
                </TabsTrigger>
                <TabsTrigger value="study" className="gap-1.5">
                  <BookOpen className="h-4 w-4" />
                  Study Guide
                </TabsTrigger>
                <TabsTrigger value="evaluation" className="gap-1.5">
                  <ShieldCheck className="h-4 w-4" />
                  Quality
                </TabsTrigger>
              </TabsList>

              {/* Transcript Tab */}
              <TabsContent value="transcript" className="mt-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Full Transcript</CardTitle>
                    <CardDescription>
                      Scene-by-scene narration ({formatDuration(totalDuration)}{" "}
                      total)
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {transcript && transcript.scenes.length > 0 ? (
                      <div className="space-y-6">
                        {transcript.scenes.map((entry, idx) => (
                          <div
                            key={entry.scene_id}
                            className={`group cursor-pointer rounded-lg p-3 -m-3 transition-colors ${
                              idx === activeSceneIdx
                                ? "bg-primary/5 ring-1 ring-primary/20"
                                : "hover:bg-muted/50"
                            }`}
                            onClick={() => seekToScene(entry.timestamp)}
                          >
                            <div className="flex items-center gap-2 mb-2">
                              <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                                idx === activeSceneIdx
                                  ? "bg-primary text-primary-foreground"
                                  : "bg-muted text-muted-foreground"
                              }`}>
                                {entry.scene_order + 1}
                              </span>
                              <h4 className="text-sm font-semibold flex-1">
                                {entry.title}
                              </h4>
                              {entry.scene_type && (
                                <Badge
                                  variant="secondary"
                                  className="text-[11px] font-medium"
                                >
                                  {SCENE_TYPE_LABELS[entry.scene_type] ||
                                    entry.scene_type}
                                </Badge>
                              )}
                              <Badge
                                variant="outline"
                                className="text-[11px] tabular-nums cursor-pointer hover:bg-primary/10"
                              >
                                <Play className="h-2.5 w-2.5 mr-1" />
                                {formatTime(entry.timestamp)} —{" "}
                                {formatDuration(entry.duration_sec)}
                              </Badge>
                            </div>
                            <div className="ml-9 pl-4 border-l-2 border-primary/20 group-hover:border-primary/40 transition-colors">
                              <p className="text-sm leading-relaxed text-foreground/80">
                                {entry.text || (
                                  <span className="italic text-muted-foreground/60">
                                    No narration text for this scene.
                                  </span>
                                )}
                              </p>
                              {entry.teaching_note && (
                                <p className="mt-2 text-xs text-muted-foreground/70 italic border-l-2 border-muted-foreground/20 pl-2">
                                  {entry.teaching_note}
                                </p>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        Transcript will be available after rendering.
                      </p>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Quiz Tab */}
              <TabsContent value="quiz" className="mt-6">
                {quiz && quiz.questions.length > 0 ? (
                  <QuizDisplay questions={quiz.questions} />
                ) : (
                  <Card>
                    <CardContent className="py-12 text-center text-muted-foreground">
                      <HelpCircle className="mx-auto mb-3 h-8 w-8 opacity-40" />
                      <p className="font-medium">No Quiz Available Yet</p>
                      <p className="text-sm mt-1 opacity-70">
                        Quiz will be generated after the lesson is complete.
                      </p>
                    </CardContent>
                  </Card>
                )}
              </TabsContent>

              {/* Key Takeaways Tab */}
              <TabsContent value="takeaways" className="mt-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Key Takeaways</CardTitle>
                    <CardDescription>
                      Learning objectives and core insights from each section
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {transcript && transcript.scenes.length > 0 ? (
                      <div className="grid gap-3 sm:grid-cols-2">
                        {transcript.scenes.map((entry) => {
                          const takeaway =
                            entry.learning_objective ||
                            extractFirstSentence(entry.text);
                          if (!takeaway) return null;
                          return (
                            <div
                              key={entry.scene_id}
                              className="flex items-start gap-3 p-4 rounded-lg border bg-card hover:bg-accent/5 transition-colors"
                            >
                              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary mt-0.5">
                                {entry.scene_order + 1}
                              </span>
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-semibold leading-tight">
                                  {entry.title}
                                </p>
                                <p className="text-sm text-muted-foreground mt-1 leading-relaxed">
                                  {takeaway}
                                </p>
                                {entry.scene_type && (
                                  <div className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground/60">
                                    <Target className="h-3 w-3" />
                                    {SCENE_TYPE_LABELS[entry.scene_type] ||
                                      entry.scene_type}
                                    <span className="mx-1">·</span>
                                    {formatDuration(entry.duration_sec)}
                                  </div>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        Key takeaways will be extracted from the lesson content.
                      </p>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Study Guide Tab */}
              <TabsContent value="study" className="mt-6 space-y-4">
                {transcript?.misconceptions &&
                  transcript.misconceptions.length > 0 && (
                    <Card>
                      <CardHeader className="pb-3">
                        <CardTitle className="text-lg flex items-center gap-2">
                          <AlertTriangle className="h-5 w-5 text-amber-500" />
                          Common Misconceptions
                        </CardTitle>
                        <CardDescription>
                          Watch out for these misunderstandings
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-3">
                          {transcript.misconceptions.map((m, i) => (
                            <div
                              key={i}
                              className="flex gap-3 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/20 border border-amber-200/50 dark:border-amber-800/30"
                            >
                              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-amber-100 dark:bg-amber-900/40 text-xs font-bold text-amber-700 dark:text-amber-400 mt-0.5">
                                !
                              </span>
                              <p className="text-sm leading-relaxed">{m}</p>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                {transcript?.prerequisites &&
                  transcript.prerequisites.length > 0 && (
                    <Card>
                      <CardHeader className="pb-3">
                        <CardTitle className="text-lg flex items-center gap-2">
                          <BookOpen className="h-5 w-5 text-blue-500" />
                          Prerequisites
                        </CardTitle>
                        <CardDescription>
                          Make sure you understand these before diving in
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="flex flex-wrap gap-2">
                          {transcript.prerequisites.map((p, i) => (
                            <span
                              key={i}
                              className="inline-flex items-center rounded-full border bg-blue-50 dark:bg-blue-950/20 border-blue-200/50 dark:border-blue-800/30 px-3 py-1 text-sm font-medium text-blue-700 dark:text-blue-400"
                            >
                              {p}
                            </span>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                {(!transcript?.misconceptions ||
                  transcript.misconceptions.length === 0) &&
                  (!transcript?.prerequisites ||
                    transcript.prerequisites.length === 0) && (
                    <Card>
                      <CardContent className="py-12 text-center text-muted-foreground">
                        <BookOpen className="mx-auto mb-3 h-8 w-8 opacity-40" />
                        <p className="font-medium">
                          Study guide will be available after lesson generation.
                        </p>
                      </CardContent>
                    </Card>
                  )}
              </TabsContent>

              {/* Evaluation / Quality Tab */}
              <TabsContent value="evaluation" className="mt-6 space-y-4">
                {evaluation ? (
                  <>
                    {/* Overall Score */}
                    <Card>
                      <CardHeader className="pb-3">
                        <div className="flex items-center justify-between">
                          <div>
                            <CardTitle className="text-lg flex items-center gap-2">
                              <ShieldCheck className="h-5 w-5 text-primary" />
                              Quality Report
                            </CardTitle>
                            <CardDescription>
                              Automated evaluation of lesson quality
                            </CardDescription>
                          </div>
                          <div className="text-right">
                            <div className={`text-3xl font-bold ${
                              evaluation.grade === "A" ? "text-green-600" :
                              evaluation.grade === "B" ? "text-blue-600" :
                              evaluation.grade === "C" ? "text-amber-600" : "text-red-600"
                            }`}>
                              {evaluation.grade}
                            </div>
                            <p className="text-xs text-muted-foreground">
                              {Math.round(evaluation.overall_score * 100)}%
                            </p>
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent>
                        <div className="grid grid-cols-3 gap-3 mb-4">
                          <div className="text-center p-2 rounded bg-red-50 dark:bg-red-950/20">
                            <p className="text-lg font-bold text-red-600">{evaluation.summary.errors}</p>
                            <p className="text-[11px] text-muted-foreground">Errors</p>
                          </div>
                          <div className="text-center p-2 rounded bg-amber-50 dark:bg-amber-950/20">
                            <p className="text-lg font-bold text-amber-600">{evaluation.summary.warnings}</p>
                            <p className="text-[11px] text-muted-foreground">Warnings</p>
                          </div>
                          <div className="text-center p-2 rounded bg-blue-50 dark:bg-blue-950/20">
                            <p className="text-lg font-bold text-blue-600">{evaluation.summary.info}</p>
                            <p className="text-[11px] text-muted-foreground">Info</p>
                          </div>
                        </div>

                        {/* Category Scores */}
                        <div className="space-y-3">
                          {[
                            { label: "Content Accuracy", data: evaluation.content_accuracy },
                            { label: "Pedagogical Quality", data: evaluation.pedagogical_quality },
                            { label: "Visual Quality", data: evaluation.visual_quality },
                            { label: "Narration Quality", data: evaluation.narration_quality },
                            { label: "Engagement", data: evaluation.engagement },
                          ].map((cat) => (
                            <div key={cat.label}>
                              <div className="flex items-center justify-between mb-1">
                                <span className="text-sm font-medium">{cat.label}</span>
                                <span className="text-sm font-bold tabular-nums">
                                  {Math.round((cat.data?.score ?? 0) * 100)}%
                                </span>
                              </div>
                              <div className="h-2 rounded-full bg-muted overflow-hidden">
                                <div
                                  className={`h-full rounded-full transition-all ${
                                    (cat.data?.score ?? 0) >= 0.85 ? "bg-green-500" :
                                    (cat.data?.score ?? 0) >= 0.7 ? "bg-blue-500" :
                                    (cat.data?.score ?? 0) >= 0.5 ? "bg-amber-500" : "bg-red-500"
                                  }`}
                                  style={{ width: `${Math.round((cat.data?.score ?? 0) * 100)}%` }}
                                />
                              </div>
                              {cat.data?.feedback && (
                                <p className="text-xs text-muted-foreground mt-1">
                                  {cat.data.feedback}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>

                    {/* Flags */}
                    {evaluation.detailed_flags && evaluation.detailed_flags.length > 0 && (
                      <Card>
                        <CardHeader className="pb-3">
                          <CardTitle className="text-lg flex items-center gap-2">
                            <BarChart3 className="h-5 w-5" />
                            Issues Found ({evaluation.detailed_flags.length})
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-2">
                            {evaluation.detailed_flags.map((flag, i) => (
                              <div
                                key={`flag-${i}`}
                                className={`flex items-start gap-2 p-2.5 rounded-lg border text-sm ${
                                  flag.severity === "error"
                                    ? "bg-red-50 dark:bg-red-950/20 border-red-200 dark:border-red-800/30"
                                    : flag.severity === "warning"
                                    ? "bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800/30"
                                    : "bg-blue-50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-800/30"
                                }`}
                              >
                                <span className={`shrink-0 text-xs font-bold uppercase px-1.5 py-0.5 rounded ${
                                  flag.severity === "error" ? "bg-red-200 text-red-800" :
                                  flag.severity === "warning" ? "bg-amber-200 text-amber-800" :
                                  "bg-blue-200 text-blue-800"
                                }`}>
                                  {flag.severity}
                                </span>
                                <span className="text-xs uppercase text-muted-foreground font-medium shrink-0">
                                  {flag.category}
                                </span>
                                <p className="text-sm flex-1">{flag.message}</p>
                              </div>
                            ))}
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    {/* Scene Confidence */}
                    {evaluation.scene_scores && evaluation.scene_scores.length > 0 && (
                      <Card>
                        <CardHeader className="pb-3">
                          <CardTitle className="text-lg">Scene Confidence</CardTitle>
                          <CardDescription>Per-scene quality scores</CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-2">
                            {evaluation.scene_scores.map((ss) => (
                              <div key={`ss-${ss.scene_index}`} className="flex items-center gap-3">
                                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-bold">
                                  {ss.scene_index + 1}
                                </span>
                                <span className="text-sm flex-1 truncate">{ss.title}</span>
                                <Badge variant={
                                  ss.confidence === "high" ? "default" :
                                  ss.confidence === "medium" ? "secondary" : "destructive"
                                } className="text-[10px]">
                                  {ss.confidence} ({Math.round(ss.score * 100)}%)
                                </Badge>
                              </div>
                            ))}
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    {/* Suggestions */}
                    {evaluation.suggestions && evaluation.suggestions.length > 0 && (
                      <Card>
                        <CardHeader className="pb-3">
                          <CardTitle className="text-lg flex items-center gap-2">
                            <Lightbulb className="h-5 w-5 text-amber-500" />
                            Suggestions
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <ul className="space-y-2">
                            {evaluation.suggestions.map((s, i) => (
                              <li key={`sug-${i}`} className="flex gap-2 text-sm">
                                <span className="text-primary font-bold shrink-0">→</span>
                                {s}
                              </li>
                            ))}
                          </ul>
                        </CardContent>
                      </Card>
                    )}

                    <Button
                      variant="outline"
                      onClick={handleRunEvaluation}
                      disabled={isEvaluating}
                      className="w-full"
                    >
                      {isEvaluating ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCw className="mr-2 h-4 w-4" />
                      )}
                      Re-run Evaluation
                    </Button>
                  </>
                ) : (
                  <Card>
                    <CardContent className="py-12 text-center">
                      <ShieldCheck className="mx-auto mb-3 h-8 w-8 opacity-40 text-muted-foreground" />
                      <p className="font-medium text-muted-foreground">No Evaluation Yet</p>
                      <p className="text-sm mt-1 text-muted-foreground/70 mb-4">
                        Run an evaluation to check lesson quality, identify issues, and get improvement suggestions.
                      </p>
                      <Button onClick={handleRunEvaluation} disabled={isEvaluating}>
                        {isEvaluating ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                          <ShieldCheck className="mr-2 h-4 w-4" />
                        )}
                        {isEvaluating ? "Evaluating..." : "Run Quality Evaluation"}
                      </Button>
                    </CardContent>
                  </Card>
                )}
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
}

function extractFirstSentence(text: string): string {
  if (!text) return "";
  const match = text.match(/^(.*?[.!?])\s/);
  if (match) return match[1];
  const short = text.substring(0, 150);
  return short.length < text.length ? short + "…" : short;
}
