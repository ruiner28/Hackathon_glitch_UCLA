function _isLocalBackendUrl(url: string): boolean {
  try {
    const u = new URL(url);
    return u.hostname === "localhost" || u.hostname === "127.0.0.1";
  } catch {
    return false;
  }
}

/**
 * Base URL for FastAPI JSON/media calls.
 * - **Browser, local dev:** empty string → fetch same-origin `/api/...` (Next.js rewrites to FastAPI). Avoids CORS and flaky `localhost`/`::1` issues.
 * - **Browser, remote API:** `NEXT_PUBLIC_API_URL` when it points to a non-local host.
 * - **Server (RSC):** direct URL to FastAPI (rewrites do not apply to server `fetch`).
 */
export function getApiBase(): string {
  if (typeof window !== "undefined") {
    const raw = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
    if (raw && !_isLocalBackendUrl(raw)) {
      return raw;
    }
    return "";
  }
  return (
    process.env.API_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://127.0.0.1:8000"
  ).replace(/\/$/, "");
}

/** Parse FastAPI/Starlette JSON errors or HTML fallback pages into a short string. */
function parseApiErrorBody(errorBody: string): string {
  const trimmed = errorBody.trim();
  if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
    try {
      const data = JSON.parse(trimmed) as {
        detail?: unknown;
        traceback?: string;
        message?: string;
      };
      let msg = "";
      if (typeof data.detail === "string") {
        msg = data.detail;
      } else if (Array.isArray(data.detail)) {
        msg = data.detail
          .map((d: unknown) =>
            typeof d === "object" && d !== null && "msg" in d
              ? String((d as { msg: string }).msg)
              : JSON.stringify(d)
          )
          .join("; ");
      } else if (data.detail != null) {
        msg = JSON.stringify(data.detail);
      } else if (typeof data.message === "string") {
        msg = data.message;
      } else {
        msg = trimmed;
      }
      if (
        typeof data.traceback === "string" &&
        process.env.NODE_ENV === "development"
      ) {
        msg = `${msg}\n\n${data.traceback.slice(0, 4000)}`;
      }
      return msg || trimmed;
    } catch {
      return trimmed.slice(0, 2000);
    }
  }
  if (trimmed.includes("<!DOCTYPE") || trimmed.includes("<html")) {
    const title = trimmed.match(/<title>([^<]+)<\/title>/i);
    if (title) {
      return `Server returned HTML: ${title[1]}. Often means the Next.js proxy could not reach FastAPI — confirm pnpm dev:api and restart Next.`;
    }
    return "Server returned an HTML error page. Check the API terminal and that port 8000 is reachable from Next.js rewrites.";
  }
  return trimmed.slice(0, 2000);
}

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const base = getApiBase();
  const label = base || `${typeof window !== "undefined" ? window.location.origin : ""} → FastAPI`;
  let res: Response;
  try {
    res = await fetch(`${base}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
      ...options,
    });
  } catch (err) {
    const msg =
      err instanceof Error ? err.message : "Network error";
    const hint =
      /hang up|ECONNRESET|ECONNREFUSED|Failed to fetch/i.test(msg)
        ? " From repo root run `pnpm dev` (starts API + Next) or a second terminal: `pnpm dev:api`. Also check `API_INTERNAL_URL` in next.config."
        : " Start the API (`pnpm dev:api` or `pnpm dev` from repo root), restart Next after changing next.config, or set API_INTERNAL_URL for rewrites.";
    throw new Error(`${msg} (${label}).${hint}`);
  }

  if (!res.ok) {
    const errorBody = await res.text().catch(() => "Unknown error");
    const message = parseApiErrorBody(errorBody);
    throw new Error(`API Error ${res.status}: ${message}`);
  }

  return res.json();
}

export async function uploadFile(file: File): Promise<{ id: string; title: string }> {
  const formData = new FormData();
  formData.append("file", file);

  const base = getApiBase();
  let res: Response;
  try {
    res = await fetch(`${base}/api/uploads`, {
      method: "POST",
      body: formData,
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Network error";
    throw new Error(`${msg} — is the API running?`);
  }

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
  const job = await request<{
    status: string;
    error_message?: string | null;
  }>(`/api/lessons/${lessonId}/render-preview`, {
    method: "POST",
  });
  if (job.status === "failed") {
    throw new Error(
      job.error_message || "Preview render failed — check API logs and FFmpeg."
    );
  }
  return job;
}

export async function triggerRenderFinal(lessonId: string) {
  const job = await request<{
    status: string;
    error_message?: string | null;
  }>(`/api/lessons/${lessonId}/render-final`, {
    method: "POST",
  });
  if (job.status === "failed") {
    throw new Error(
      job.error_message ||
        "Final render failed — FFmpeg is required locally; Gemini is not used for this step."
    );
  }
  return job;
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
  return `${getApiBase()}/api/lessons/${lessonId}/video`;
}

export function getSubtitlesUrl(lessonId: string): string {
  return `${getApiBase()}/api/lessons/${lessonId}/subtitles`;
}

export async function checkSubtitlesReady(lessonId: string): Promise<boolean> {
  try {
    const res = await fetch(`${getApiBase()}/api/lessons/${lessonId}/subtitles`, {
      method: "HEAD",
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function checkVideoReady(lessonId: string): Promise<boolean> {
  try {
    const res = await fetch(`${getApiBase()}/api/lessons/${lessonId}/video`, {
      method: "HEAD",
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function downloadLesson(lessonId: string) {
  const url = `${getApiBase()}/api/lessons/${lessonId}/download`;
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
  await triggerGenerateDiagram(lessonId).catch(() => {});
  await triggerCompileScenes(lessonId);
  await triggerGenerateAssets(lessonId);
  await triggerRenderPreview(lessonId);
}

export interface DiagramData {
  diagram_spec: Record<string, unknown>;
  walkthrough_states: WalkthroughState[];
}

export interface WalkthroughState {
  state_id: string;
  title: string;
  narration: string;
  focus_regions: string[];
  highlight_paths: string[];
  dim_regions: string[];
  overlay_mode: string | null;
  duration_sec: number;
  user_question_hooks?: string[];
}

export async function getDiagramData(lessonId: string): Promise<DiagramData> {
  return request<DiagramData>(`/api/lessons/${lessonId}/diagram-data`);
}

export function getDiagramSvgUrl(lessonId: string, stateId?: string): string {
  const base = `${getApiBase()}/api/lessons/${lessonId}/diagram`;
  if (stateId) return `${base}?state_id=${encodeURIComponent(stateId)}`;
  return base;
}

export function getLiveWebSocketUrl(lessonId: string): string {
  const base = getApiBase() || "http://127.0.0.1:8000";
  return base.replace(/^http/, "ws").replace(/\/$/, "") +
    `/api/lessons/${lessonId}/live`;
}

export async function triggerGenerateDiagram(lessonId: string) {
  return request<{
    diagram_spec: Record<string, unknown>;
    walkthrough_states: WalkthroughState[];
    state_count: number;
  }>(`/api/lessons/${lessonId}/generate-diagram`, {
    method: "POST",
  });
}
