const API_BASE =
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

export async function uploadFile(lessonId: string, file: File) {
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
    }>
  >(`/api/lessons/${lessonId}/scenes`);
}

export async function updateScene(
  sceneId: string,
  data: {
    narration_text?: string;
    on_screen_text?: string[];
    duration_sec?: number;
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
  return request(`/api/lessons/${lessonId}/evaluate`, {
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
    scenes: Array<{
      scene_id: string;
      scene_order: number;
      title: string;
      text: string;
      timestamp: number;
      duration_sec: number;
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

export async function downloadLesson(lessonId: string) {
  return request<{
    lesson_id: string;
    title: string;
    status: string;
    job_type: string;
    rendered_at: string | null;
    message: string;
  }>(`/api/lessons/${lessonId}/download`);
}

export async function runFullPipeline(lessonId: string) {
  await triggerExtract(lessonId);
  await triggerPlan(lessonId);
  await triggerCompileScenes(lessonId);
  await triggerGenerateAssets(lessonId);
  await triggerRenderPreview(lessonId);
}
