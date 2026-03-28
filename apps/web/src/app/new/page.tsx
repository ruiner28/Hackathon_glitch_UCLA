"use client";

import { useState, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useDropzone } from "react-dropzone";
import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TopicSuggestions } from "@/components/lesson/topic-suggestions";
import { createTopicLesson, uploadFile } from "@/lib/api";
import {
  Loader2,
  Upload,
  FileText,
  X,
  Sparkles,
  PenLine,
} from "lucide-react";

const topicSchema = z.object({
  topic: z.string().min(3, "Topic must be at least 3 characters"),
  domain: z.string().min(1, "Please select a domain"),
  style_preset: z.string().min(1, "Please select a style"),
  duration_seconds: z.number().min(30).max(600),
  music_enabled: z.boolean(),
});

type TopicFormData = z.infer<typeof topicSchema>;

function NewLessonContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const prefilledTopic = searchParams.get("topic") || "";

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState("");
  const [activeTab, setActiveTab] = useState(
    prefilledTopic ? "topic" : "topic"
  );

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<TopicFormData>({
    resolver: zodResolver(topicSchema),
    defaultValues: {
      topic: prefilledTopic,
      domain: "cs_concepts",
      style_preset: "clean_academic",
      duration_seconds: 120,
      music_enabled: true,
    },
  });

  const currentTopic = watch("topic");
  const currentDuration = watch("duration_seconds");
  const musicEnabled = watch("music_enabled");

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setUploadError("");
    const file = acceptedFiles[0];
    if (!file) return;

    const validTypes = [
      "application/pdf",
      "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ];
    if (!validTypes.includes(file.type)) {
      setUploadError("Please upload a PDF or PPTX file.");
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      setUploadError("File size must be under 50MB.");
      return;
    }

    setUploadedFile(file);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        [".pptx"],
    },
    maxFiles: 1,
  });

  async function onSubmitTopic(data: TopicFormData) {
    setIsSubmitting(true);
    try {
      const lesson = await createTopicLesson(data);
      router.push(`/processing/${lesson.id}`);
    } catch (err) {
      console.error("Failed to create lesson:", err);
      setIsSubmitting(false);
    }
  }

  async function onSubmitUpload() {
    if (!uploadedFile) return;
    setIsSubmitting(true);
    try {
      const lesson = await createTopicLesson({
        topic: uploadedFile.name.replace(/\.[^/.]+$/, ""),
        domain: "cs_concepts",
        style_preset: "clean_academic",
        duration_seconds: 120,
        music_enabled: true,
      });
      await uploadFile(lesson.id, uploadedFile);
      router.push(`/processing/${lesson.id}`);
    } catch (err) {
      console.error("Failed to upload:", err);
      setIsSubmitting(false);
    }
  }

  function formatBytes(bytes: number) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  return (
    <>
      <Header />
      <main className="flex-1 gradient-bg">
        <div className="container py-12">
          <div className="mx-auto max-w-2xl">
            <div className="mb-8 text-center">
              <h1 className="text-3xl font-bold tracking-tight">
                Create a New Lesson
              </h1>
              <p className="mt-2 text-muted-foreground">
                Enter a topic or upload materials to generate a visual lesson
              </p>
            </div>

            <Card className="shadow-lg">
              <CardContent className="pt-6">
                <Tabs
                  value={activeTab}
                  onValueChange={setActiveTab}
                >
                  <TabsList className="grid w-full grid-cols-2">
                    <TabsTrigger value="topic" className="gap-1.5">
                      <PenLine className="h-4 w-4" />
                      Enter Topic
                    </TabsTrigger>
                    <TabsTrigger value="upload" className="gap-1.5">
                      <Upload className="h-4 w-4" />
                      Upload File
                    </TabsTrigger>
                  </TabsList>

                  {/* Topic Tab */}
                  <TabsContent value="topic" className="mt-6">
                    <form
                      onSubmit={handleSubmit(onSubmitTopic)}
                      className="space-y-6"
                    >
                      <div className="space-y-2">
                        <Label htmlFor="topic">Topic</Label>
                        <Input
                          id="topic"
                          placeholder="e.g. How TCP three-way handshake works"
                          {...register("topic")}
                        />
                        {errors.topic && (
                          <p className="text-sm text-destructive">
                            {errors.topic.message}
                          </p>
                        )}
                      </div>

                      <TopicSuggestions
                        onSelect={(topic) => setValue("topic", topic)}
                        selectedTopic={currentTopic}
                      />

                      <div className="grid gap-4 sm:grid-cols-2">
                        <div className="space-y-2">
                          <Label>Domain</Label>
                          <Select
                            defaultValue="cs_concepts"
                            onValueChange={(v) => setValue("domain", v)}
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="cs_concepts">
                                CS Concepts
                              </SelectItem>
                              <SelectItem value="system_design">
                                System Design
                              </SelectItem>
                            </SelectContent>
                          </Select>
                        </div>

                        <div className="space-y-2">
                          <Label>Style Preset</Label>
                          <Select
                            defaultValue="clean_academic"
                            onValueChange={(v) => setValue("style_preset", v)}
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="clean_academic">
                                Clean Academic
                              </SelectItem>
                              <SelectItem value="modern_technical">
                                Modern Technical
                              </SelectItem>
                              <SelectItem value="cinematic_minimal">
                                Cinematic Minimal
                              </SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>

                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <Label>
                            Duration: {Math.floor(currentDuration / 60)}:
                            {String(currentDuration % 60).padStart(2, "0")}
                          </Label>
                          <span className="text-xs text-muted-foreground">
                            30s – 10min
                          </span>
                        </div>
                        <input
                          type="range"
                          min={30}
                          max={600}
                          step={30}
                          value={currentDuration}
                          onChange={(e) =>
                            setValue(
                              "duration_seconds",
                              parseInt(e.target.value)
                            )
                          }
                          className="w-full accent-primary"
                        />
                      </div>

                      <div className="flex items-center justify-between rounded-lg border p-4">
                        <div>
                          <Label>Background Music</Label>
                          <p className="text-xs text-muted-foreground">
                            Add subtle background music to the lesson
                          </p>
                        </div>
                        <Switch
                          checked={musicEnabled}
                          onCheckedChange={(v) => setValue("music_enabled", v)}
                        />
                      </div>

                      <Button
                        type="submit"
                        className="w-full"
                        size="lg"
                        disabled={isSubmitting}
                      >
                        {isSubmitting ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Creating Lesson...
                          </>
                        ) : (
                          <>
                            <Sparkles className="mr-2 h-4 w-4" />
                            Generate Lesson
                          </>
                        )}
                      </Button>
                    </form>
                  </TabsContent>

                  {/* Upload Tab */}
                  <TabsContent value="upload" className="mt-6 space-y-6">
                    {!uploadedFile ? (
                      <div
                        {...getRootProps()}
                        className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-12 text-center transition-colors cursor-pointer ${
                          isDragActive
                            ? "border-primary bg-primary/5"
                            : "border-border hover:border-primary/50 hover:bg-muted/50"
                        }`}
                      >
                        <input {...getInputProps()} />
                        <Upload className="mb-4 h-10 w-10 text-muted-foreground" />
                        <p className="text-sm font-medium">
                          {isDragActive
                            ? "Drop your file here"
                            : "Drag & drop your file here"}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          PDF or PPTX up to 50MB
                        </p>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="mt-4"
                        >
                          Browse Files
                        </Button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-4 rounded-lg border bg-muted/50 p-4">
                        <FileText className="h-10 w-10 text-primary" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">
                            {uploadedFile.name}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {formatBytes(uploadedFile.size)}
                          </p>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setUploadedFile(null)}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    )}

                    {uploadError && (
                      <p className="text-sm text-destructive">{uploadError}</p>
                    )}

                    <Button
                      className="w-full"
                      size="lg"
                      disabled={!uploadedFile || isSubmitting}
                      onClick={onSubmitUpload}
                    >
                      {isSubmitting ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Uploading & Creating...
                        </>
                      ) : (
                        <>
                          <Sparkles className="mr-2 h-4 w-4" />
                          Generate Lesson
                        </>
                      )}
                    </Button>
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}

export default function NewLessonPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      }
    >
      <NewLessonContent />
    </Suspense>
  );
}
