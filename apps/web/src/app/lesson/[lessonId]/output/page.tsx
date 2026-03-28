"use client";

import { useEffect, useState, use } from "react";
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
import { Separator } from "@/components/ui/separator";
import { QuizDisplay } from "@/components/lesson/quiz-display";
import { getLesson, getTranscript, getQuiz, downloadLesson } from "@/lib/api";
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
} from "lucide-react";

interface TranscriptScene {
  scene_id: string;
  scene_order: number;
  title: string;
  text: string;
  timestamp: number;
  duration_sec: number;
}

interface TranscriptData {
  full_text: string;
  total_duration_sec: number;
  scenes: TranscriptScene[];
}

interface QuizData {
  questions: Array<{
    question: string;
    options: string[];
    correct_index: number;
    explanation: string;
  }>;
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

  useEffect(() => {
    async function load() {
      try {
        const [lesson, transcriptData, quizData] = await Promise.all([
          getLesson(lessonId),
          getTranscript(lessonId).catch(() => null),
          getQuiz(lessonId).catch(() => null),
        ]);

        setLessonTitle(lesson.title);
        setLessonSummary(lesson.summary || "");
        setLessonDomain(lesson.domain);
        setTranscript(transcriptData);
        setQuiz(quizData);
      } catch (err) {
        console.error("Failed to load output:", err);
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [lessonId]);

  async function handleDownload() {
    setDownloadStatus("loading");
    try {
      const result = await downloadLesson(lessonId);
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
        <main className="flex flex-1 items-center justify-center min-h-screen">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </main>
      </>
    );
  }

  const sceneCount = transcript?.scenes.length || 0;
  const totalDuration = transcript?.total_duration_sec || 0;

  return (
    <>
      <Header />
      <main className="flex-1">
        <div className="container py-8">
          <div className="mx-auto max-w-4xl">
            {/* Back Link */}
            <Button
              variant="ghost"
              size="sm"
              className="mb-4 -ml-2"
              onClick={() => router.push(`/lesson/${lessonId}`)}
            >
              <ArrowLeft className="mr-1.5 h-4 w-4" />
              Back to Editor
            </Button>

            {/* Header */}
            <div className="mb-6">
              <div className="flex items-start justify-between">
                <div>
                  <h1 className="text-3xl font-bold">{lessonTitle}</h1>
                  {lessonSummary && (
                    <p className="mt-2 text-muted-foreground max-w-2xl">
                      {lessonSummary}
                    </p>
                  )}
                </div>
                <Badge variant="outline" className="mt-1 capitalize">
                  {lessonDomain.replace(/_/g, " ")}
                </Badge>
              </div>

              {/* Stats Row */}
              <div className="mt-4 flex items-center gap-4 text-sm text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  <Film className="h-4 w-4" />
                  {sceneCount} scenes
                </span>
                <span className="flex items-center gap-1.5">
                  <Clock className="h-4 w-4" />
                  {formatDuration(totalDuration)}
                </span>
                {quiz && (
                  <span className="flex items-center gap-1.5">
                    <HelpCircle className="h-4 w-4" />
                    {quiz.questions.length} quiz questions
                  </span>
                )}
              </div>
            </div>

            {/* Video Player Placeholder */}
            <div className="mb-8">
              <div className="aspect-video rounded-xl bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center shadow-xl border border-slate-700/50 overflow-hidden relative">
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_rgba(59,130,246,0.08),transparent_70%)]" />
                <div className="text-center relative z-10">
                  <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-white/5 border border-white/10">
                    <Play className="h-10 w-10 text-white/50" />
                  </div>
                  <p className="text-base font-medium text-white/70">
                    Video Assembly in Progress
                  </p>
                  <p className="mt-1 text-sm text-white/40 max-w-sm">
                    All {sceneCount} scenes have been rendered. Full MP4 export
                    via Remotion + FFmpeg coming soon.
                  </p>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="mb-8 flex items-center gap-3">
              <Button onClick={handleDownload} disabled={downloadStatus === "loading"}>
                {downloadStatus === "loading" ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : downloadStatus === "done" ? (
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                ) : (
                  <Download className="mr-2 h-4 w-4" />
                )}
                {downloadStatus === "done"
                  ? "Render Info Retrieved"
                  : downloadStatus === "error"
                  ? "Not Available Yet"
                  : "Download Info"}
              </Button>
              <Button
                variant="outline"
                onClick={() => router.push(`/lesson/${lessonId}`)}
              >
                <BookOpen className="mr-2 h-4 w-4" />
                Edit Scenes
              </Button>
            </div>

            {/* Tabs */}
            <Tabs defaultValue="transcript" className="w-full">
              <TabsList className="grid w-full grid-cols-3">
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
                  Key Takeaways
                </TabsTrigger>
              </TabsList>

              {/* Transcript Tab */}
              <TabsContent value="transcript" className="mt-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Full Transcript</CardTitle>
                    <CardDescription>
                      Scene-by-scene narration for the entire lesson
                      ({formatDuration(totalDuration)} total)
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {transcript && transcript.scenes.length > 0 ? (
                      <div className="space-y-6">
                        {transcript.scenes.map((entry) => (
                          <div key={entry.scene_id}>
                            <div className="flex items-center gap-2 mb-2">
                              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                                {entry.scene_order + 1}
                              </span>
                              <h4 className="text-sm font-semibold">
                                {entry.title}
                              </h4>
                              <Badge variant="outline" className="text-xs ml-auto">
                                {formatTime(entry.timestamp)} — {formatDuration(entry.duration_sec)}
                              </Badge>
                            </div>
                            <div className="ml-8 pl-4 border-l-2 border-primary/15">
                              <p className="text-sm leading-relaxed text-muted-foreground">
                                {entry.text || (
                                  <span className="italic opacity-60">
                                    No narration text for this scene.
                                  </span>
                                )}
                              </p>
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
                    <CardContent className="py-8 text-center text-muted-foreground">
                      <HelpCircle className="mx-auto mb-3 h-8 w-8 opacity-50" />
                      <p>Quiz will be generated after the lesson is complete.</p>
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
                      The most important concepts from each scene
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {transcript && transcript.scenes.length > 0 ? (
                      <div className="space-y-4">
                        {transcript.scenes.map((entry) => {
                          const firstSentence = extractFirstSentence(entry.text);
                          if (!firstSentence) return null;
                          return (
                            <div
                              key={entry.scene_id}
                              className="flex items-start gap-3 p-3 rounded-lg bg-muted/50"
                            >
                              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary mt-0.5">
                                {entry.scene_order + 1}
                              </span>
                              <div>
                                <p className="text-sm font-medium">
                                  {entry.title}
                                </p>
                                <p className="text-sm text-muted-foreground mt-0.5">
                                  {firstSentence}
                                </p>
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
  const short = text.substring(0, 120);
  return short.length < text.length ? short + "..." : short;
}
