"use client";

import { useState, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useDropzone } from "react-dropzone";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
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
import { createTopicLesson, uploadFile, createLessonFromDocument } from "@/lib/api";
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

const SHOWCASE_TOPIC_DOMAIN: Record<string, string> = {
  "Rate Limiter": "system_design",
  "OS Deadlock": "cs_concepts",
  "Compiler Bottom-Up Parsing": "cs_concepts",
};

function NewLessonContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const prefilledTopic = searchParams.get("topic") || "";

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState("");
  const [activeTab, setActiveTab] = useState("topic");

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
      domain:
        (prefilledTopic && SHOWCASE_TOPIC_DOMAIN[prefilledTopic]) ||
        "cs_concepts",
      style_preset: "clean_academic",
      duration_seconds: 120,
      music_enabled: false,
    },
  });

  const currentTopic = watch("topic");
  const currentDomain = watch("domain");

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
      const doc = await uploadFile(uploadedFile);
      const paperTitle = doc.title || uploadedFile.name.replace(/\.[^/.]+$/, "");
      const lesson = await createLessonFromDocument({
        source_document_id: doc.id,
        topic: paperTitle,
        domain: "cs",
        style_preset: "clean_academic",
      });
      router.push(`/processing/${lesson.id}`);
    } catch (err) {
      console.error("Failed to upload:", err);
      setUploadError("Upload failed. Please try again.");
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
      <main className="min-h-screen flex-1 bg-[hsl(var(--page-bg))]">
        <div className="mx-auto max-w-xl px-6 py-12 sm:py-16">
          <div className="mb-8 text-center">
            <p className="section-label mb-2">Create</p>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">
              New Deep Dive
            </h1>
            <p className="mt-2 text-sm text-slate-600">
              Enter a CS topic or upload a paper to generate an interactive lesson
            </p>
          </div>

          <Card className="border-slate-200/90 shadow-sm ring-1 ring-slate-900/[0.03]">
            <CardContent className="pt-6">
              <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="grid w-full grid-cols-2 mb-6">
                  <TabsTrigger value="topic" className="gap-1.5">
                    <PenLine className="h-3.5 w-3.5" />
                    Topic
                  </TabsTrigger>
                  <TabsTrigger value="upload" className="gap-1.5">
                    <Upload className="h-3.5 w-3.5" />
                    Upload
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="topic">
                  <form
                    onSubmit={handleSubmit(onSubmitTopic)}
                    className="space-y-5"
                  >
                    <div className="space-y-1.5">
                      <Label htmlFor="topic" className="text-slate-700">
                        What do you want to learn?
                      </Label>
                      <Input
                        id="topic"
                        placeholder="e.g. Rate Limiter, TCP Handshake, B-Trees..."
                        className="h-11"
                        {...register("topic")}
                      />
                      {errors.topic && (
                        <p className="text-sm text-destructive">
                          {errors.topic.message}
                        </p>
                      )}
                    </div>

                    <TopicSuggestions
                      onSelect={(topic, domain) => {
                        setValue("topic", topic);
                        if (domain) setValue("domain", domain);
                      }}
                      selectedTopic={currentTopic}
                    />

                    <div className="space-y-1.5">
                      <Label className="text-slate-700">Domain</Label>
                      <Select
                        value={currentDomain}
                        onValueChange={(v) => setValue("domain", v)}
                      >
                        <SelectTrigger className="h-10">
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

                    <Button
                      type="submit"
                      className="w-full h-11"
                      disabled={isSubmitting}
                    >
                      {isSubmitting ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Creating...
                        </>
                      ) : (
                        <>
                          <Sparkles className="mr-2 h-4 w-4" />
                          Generate Interactive Lesson
                        </>
                      )}
                    </Button>
                  </form>
                </TabsContent>

                <TabsContent value="upload" className="space-y-5">
                  {!uploadedFile ? (
                    <div
                      {...getRootProps()}
                      className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-10 text-center transition-colors cursor-pointer ${
                        isDragActive
                          ? "border-primary bg-primary/5"
                          : "border-slate-200 hover:border-primary/40 hover:bg-slate-50"
                      }`}
                    >
                      <input {...getInputProps()} />
                      <Upload className="mb-3 h-8 w-8 text-slate-300" />
                      <p className="text-sm font-medium text-slate-600">
                        {isDragActive
                          ? "Drop your file here"
                          : "Drag & drop a PDF or PPTX"}
                      </p>
                      <p className="mt-1 text-xs text-slate-400">Up to 50MB</p>
                    </div>
                  ) : (
                    <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
                      <FileText className="h-8 w-8 text-primary shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate text-slate-700">
                          {uploadedFile.name}
                        </p>
                        <p className="text-xs text-slate-400">
                          {formatBytes(uploadedFile.size)}
                        </p>
                      </div>
                      <button
                        onClick={() => setUploadedFile(null)}
                        className="p-1 rounded hover:bg-slate-200 transition-colors"
                      >
                        <X className="h-4 w-4 text-slate-400" />
                      </button>
                    </div>
                  )}

                  {uploadError && (
                    <p className="text-sm text-destructive">{uploadError}</p>
                  )}

                  <Button
                    className="w-full h-11"
                    disabled={!uploadedFile || isSubmitting}
                    onClick={onSubmitUpload}
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Processing...
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
      </main>
    </>
  );
}

export default function NewLessonPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-[hsl(var(--page-bg))]">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm text-slate-500">Loading…</p>
        </div>
      }
    >
      <NewLessonContent />
    </Suspense>
  );
}
