export interface SourceDocument {
  id: string;
  type: "topic" | "pdf" | "pptx";
  title: string;
  original_filename: string | null;
  storage_url: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Lesson {
  id: string;
  source_document_id: string | null;
  input_topic: string | null;
  domain: string;
  title: string;
  summary: string | null;
  target_audience: string;
  style_preset: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface LessonDetail extends Lesson {
  scenes: Scene[];
}

export type SceneRenderMode = "auto" | "force_static" | "force_veo";

export interface Scene {
  id: string;
  lesson_id: string;
  scene_order: number;
  scene_type: string;
  title: string;
  duration_sec: number;
  render_strategy: string;
  source_refs_json: string[] | null;
  narration_text: string | null;
  on_screen_text_json: string[] | null;
  scene_spec_json: Record<string, unknown> | null;
  status: string;
  created_at: string;
  updated_at: string;
  /** API path e.g. /api/scenes/{id}/thumbnail — prefix with API base for <img src>. */
  preview_image_url?: string | null;
}

export interface SceneAsset {
  id: string;
  scene_id: string;
  asset_type: string;
  provider: string;
  prompt_version: string | null;
  storage_url: string;
  metadata_json: Record<string, unknown> | null;
  status: string;
  created_at: string;
}

export interface LessonPlan {
  id: string;
  lesson_id: string;
  concept_graph_json: Record<string, unknown>;
  prerequisites_json: unknown[];
  misconceptions_json: unknown[];
  lesson_objectives_json: unknown[];
  plan_json: Record<string, unknown>;
  created_at: string;
}

export interface EvaluationReport {
  id: string;
  lesson_id: string;
  report_json: Record<string, unknown>;
  score_overall: number;
  flags_json: string[] | null;
  created_at: string;
}

export interface QuizQuestion {
  question: string;
  options: string[];
  correct_index: number;
  explanation: string;
}

export interface TranscriptEntry {
  scene_id: string;
  text: string;
  timestamp: number;
}

export type ProcessingStep =
  | "extraction"
  | "planning"
  | "diagram_generation"
  | "scene_compilation"
  | "asset_generation"
  | "rendering";

export type StepStatus = "pending" | "active" | "complete" | "error";

export interface ProcessingStatus {
  current_step: ProcessingStep;
  steps: Record<ProcessingStep, StepStatus>;
  message: string;
}
