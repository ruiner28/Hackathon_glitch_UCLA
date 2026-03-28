export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const errorBody = await res.text().catch(() => "Unknown error");
    throw new Error(`API Error ${res.status}: ${errorBody}`);
  }

  return res.json();
}

export async function uploadFile(file: File): Promise<{ id: string; title: string }> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/api/uploads`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error(`Upload failed: ${res.status}`);
  }

  return res.json();
}

export async function createLessonFromDocument(data: {
  source_document_id: string;
  topic: string;
  domain: string;
  style_preset: string;
}) {
  return request<{
    id: string;
    title: string;
    domain: string;
    status: string;
  }>("/api/lessons", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function createTopicLesson(data: {
  topic: string;
  domain: string;
  style_preset: string;
  duration_seconds?: number;
  music_enabled?: boolean;
}) {
  const domainMap: Record<string, string> = {
    cs_concepts: "cs",
    system_design: "system_design",
    cs: "cs",
  };

  return request<{
    id: string;
    title: string;
    domain: string;
    status: string;
    style_preset: string;
    created_at: string;
    updated_at: string;
  }>("/api/lessons", {
    method: "POST",
    body: JSON.stringify({
      topic: data.topic,
      domain: domainMap[data.domain] || "cs",
      style_preset: data.style_preset,
    }),
  });
}

export async function getLesson(lessonId: string) {
  return request<{
    id: string;
    title: string;
    input_topic: string | null;
    summary: string | null;
    domain: string;
    style_preset: string;
    target_audience: string;
    status: string;
    created_at: string;
    updated_at: string;
    scenes: Array<{
      id: string;
      lesson_id: string;
      scene_order: number;
      title: string;
      scene_type: string;
      duration_sec: number;
      render_strategy: string;
      narration_text: string | null;
      on_screen_text_json: string[] | null;
      source_refs_json: string[] | null;
      status: string;
    }>;
  }>(`/api/lessons/${lessonId}`);
}

export async function getLessonScenes(lessonId: string) {
  return request<
    Array<{
      id: string;
      lesson_id: string;
      scene_order: number;
      title: string;
      scene_type: string;
      render_strategy: string;
      duration_sec: number;
      narration_text: string | null;
      on_screen_text_json: string[] | null;
      source_refs_json: string[] | null;
      scene_spec_json: Record<string, unknown> | null;
      status: string;
      created_at: string;
      updated_at: string;
      preview_image_url?: string | null;
    }>
  >(`/api/lessons/${lessonId}/scenes`);
}

export async function updateScene(
  sceneId: string,
  data: {
    narration_text?: string;
    on_screen_text?: string[];
    duration_sec?: number;
    veo_eligible?: boolean;
    render_mode?: "auto" | "force_static" | "force_veo";
  }
) {
  return request(`/api/scenes/${sceneId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function regenerateScene(sceneId: string) {
  return request(`/api/scenes/${sceneId}/regenerate`, {
    method: "POST",
  });
}

export async function regenerateSceneAssets(sceneId: string) {
  return request(`/api/scenes/${sceneId}/regenerate-assets`, {
    method: "POST",
  });
}

export async function reorderScenes(lessonId: string, sceneIds: string[]) {
  return request(`/api/lessons/${lessonId}/reorder-scenes`, {
    method: "POST",
    body: JSON.stringify({ scene_ids: sceneIds }),
  });
}

export async function updateLessonStyle(lessonId: string, stylePreset: string) {
  return request<{
    id: string;
    title: string;
    style_preset: string;
    status: string;
  }>(`/api/lessons/${lessonId}/style`, {
    method: "PATCH",
    body: JSON.stringify({ style_preset: stylePreset }),
  });
}

export async function toggleSceneVeo(sceneId: string, veoEligible: boolean) {
  return request(`/api/scenes/${sceneId}`, {
    method: "PATCH",
    body: JSON.stringify({ veo_eligible: veoEligible }),
  });
}

export async function triggerExtract(lessonId: string) {
  return request(`/api/lessons/${lessonId}/extract`, {
    method: "POST",
  });
}

export async function triggerPlan(lessonId: string) {
  return request(`/api/lessons/${lessonId}/plan`, {
    method: "POST",
  });
}

export async function triggerCompileScenes(lessonId: string) {
  return request(`/api/lessons/${lessonId}/compile-scenes`, {
    method: "POST",
  });
}

export async function triggerGenerateAssets(lessonId: string) {
  return request(`/api/lessons/${lessonId}/generate-assets`, {
    method: "POST",
  });
}

export async function triggerRenderPreview(lessonId: string) {
  return request(`/api/lessons/${lessonId}/render-preview`, {
    method: "POST",
  });
}

export async function triggerRenderFinal(lessonId: string) {
  return request(`/api/lessons/${lessonId}/render-final`, {
    method: "POST",
  });
}

export async function triggerEvaluate(lessonId: string) {
  return request<{
    id: string;
    lesson_id: string;
    report_json: Record<string, unknown>;
    score_overall: number;
    flags_json: string[] | null;
    created_at: string;
  }>(`/api/lessons/${lessonId}/evaluate`, {
    method: "POST",
  });
}

export async function getEvaluation(lessonId: string) {
  return request<{
    id: string;
    lesson_id: string;
    report_json: Record<string, unknown>;
    score_overall: number;
    flags_json: string[] | null;
    created_at: string;
  }>(`/api/lessons/${lessonId}/evaluation`);
}

export async function getTranscript(lessonId: string) {
  return request<{
    full_text: string;
    total_duration_sec: number;
    misconceptions: string[];
    prerequisites: string[];
    scenes: Array<{
      scene_id: string;
      scene_order: number;
      title: string;
      text: string;
      timestamp: number;
      duration_sec: number;
      scene_type: string;
      learning_objective: string;
      teaching_note: string;
    }>;
  }>(`/api/lessons/${lessonId}/transcript`);
}

export async function getQuiz(lessonId: string) {
  return request<{
    questions: Array<{
      question: string;
      options: string[];
      correct_index: number;
      explanation: string;
    }>;
  }>(`/api/lessons/${lessonId}/quiz`);
}

export async function getSceneInteractions(lessonId: string) {
  return request<{
    lesson_id: string;
    scene_count: number;
    total_duration_sec: number;
    prerequisites: string[];
    misconceptions: string[];
    scenes: Array<{
      scene_id: string;
      scene_order: number;
      title: string;
      scene_type: string;
      timestamp_sec: number;
      duration_sec: number;
      learning_objective: string;
      teaching_note: string;
      narration_summary: string;
      interaction_hooks: Record<string, string>;
    }>;
  }>(`/api/lessons/${lessonId}/scene-interactions`);
}

export function getVideoUrl(lessonId: string): string {
  return `${API_BASE}/api/lessons/${lessonId}/video`;
}

export function getSubtitlesUrl(lessonId: string): string {
  return `${API_BASE}/api/lessons/${lessonId}/subtitles`;
}

export async function checkSubtitlesReady(lessonId: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/lessons/${lessonId}/subtitles`, {
      method: "HEAD",
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function checkVideoReady(lessonId: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/lessons/${lessonId}/video`, {
      method: "HEAD",
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function downloadLesson(lessonId: string) {
  const url = `${API_BASE}/api/lessons/${lessonId}/download`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Download failed: ${res.status}`);
  }

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("video/")) {
    const blob = await res.blob();
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = "lesson.mp4";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(blobUrl);
    return { status: "downloaded" };
  }

  return res.json();
}

export async function runFullPipeline(lessonId: string) {
  await triggerExtract(lessonId);
  await triggerPlan(lessonId);
  await triggerCompileScenes(lessonId);
  await triggerGenerateAssets(lessonId);
  await triggerRenderPreview(lessonId);
}
