import { z } from 'zod';

import { SceneSchema } from './scene';

export const SourceDocumentTypeSchema = z.enum(['topic', 'pdf', 'pptx']);

export const SourceDocumentStatusSchema = z.enum(['uploaded', 'processing', 'ready', 'error']);

export const FragmentKindSchema = z.enum(['title', 'bullet', 'paragraph', 'note', 'figure', 'synthetic']);

export const LessonDomainSchema = z.enum(['cs', 'system_design', 'ppt_lesson']);

export const StylePresetSchema = z.enum(['clean_academic', 'modern_technical', 'cinematic_minimal']);

export const LessonStatusSchema = z.enum([
  'created',
  'extracting',
  'planning',
  'compiling',
  'generating_assets',
  'rendering',
  'completed',
  'error',
]);

export const AssetTypeSchema = z.enum(['image', 'video', 'audio', 'svg', 'json_data', 'subtitle']);

export const AssetStatusSchema = z.enum(['pending', 'generating', 'ready', 'error']);

export const RenderJobStatusSchema = z.enum(['queued', 'running', 'completed', 'failed']);

export const LessonSchema = z.object({
  id: z.string().uuid(),
  source_document_id: z.string().uuid().nullable(),
  input_topic: z.string().nullable(),
  domain: LessonDomainSchema,
  title: z.string(),
  summary: z.string().nullable(),
  target_audience: z.string(),
  style_preset: StylePresetSchema,
  status: LessonStatusSchema,
  created_at: z.string(),
  updated_at: z.string().nullable().optional(),
});

export const SourceDocumentSchema = z.object({
  id: z.string().uuid(),
  type: SourceDocumentTypeSchema,
  title: z.string(),
  original_filename: z.string().nullable().optional(),
  storage_url: z.string().nullable().optional(),
  normalized_pdf_url: z.string().nullable().optional(),
  metadata_json: z.record(z.unknown()).nullable().optional(),
  status: SourceDocumentStatusSchema,
  created_at: z.string(),
  updated_at: z.string().nullable().optional(),
});

export const SourceFragmentSchema = z.object({
  id: z.string().uuid(),
  source_document_id: z.string().uuid(),
  ref_key: z.string(),
  page_or_slide_number: z.number().int().nullable().optional(),
  kind: FragmentKindSchema,
  text: z.string(),
  bbox_json: z.record(z.unknown()).nullable().optional(),
  image_url: z.string().nullable().optional(),
});

export const LessonPlanSchema = z.object({
  id: z.string().uuid(),
  lesson_id: z.string().uuid(),
  concept_graph_json: z.record(z.unknown()).nullable().optional(),
  prerequisites_json: z.array(z.unknown()).nullable().optional(),
  misconceptions_json: z.array(z.unknown()).nullable().optional(),
  lesson_objectives_json: z.array(z.unknown()).nullable().optional(),
  plan_json: z.record(z.unknown()).nullable().optional(),
  created_at: z.string(),
});

export const LessonPlanSectionSchema = z.object({
  title: z.string(),
  objective: z.string().default(''),
  scene_type: z.string().default('deterministic_animation'),
  duration_sec: z.number().default(30),
  key_points: z.array(z.string()).default([]),
  visual_strategy: z.string().default(''),
});

export const PlannedLessonSchema = z.object({
  lesson_title: z.string(),
  target_audience: z.string().default('undergraduate CS student'),
  estimated_duration_sec: z.number().default(300),
  objectives: z.array(z.string()).default([]),
  prerequisites: z.array(z.string()).default([]),
  misconceptions: z.array(z.string()).default([]),
  sections: z.array(LessonPlanSectionSchema).default([]),
});

export const SceneAssetSchema = z.object({
  id: z.string().uuid(),
  scene_id: z.string().uuid(),
  asset_type: AssetTypeSchema,
  provider: z.string(),
  prompt_version: z.string().nullable().optional(),
  storage_url: z.string(),
  metadata_json: z.record(z.unknown()).nullable().optional(),
  status: AssetStatusSchema,
  created_at: z.string(),
});

export const RenderJobSchema = z.object({
  id: z.string().uuid(),
  lesson_id: z.string().uuid(),
  job_type: z.string(),
  status: RenderJobStatusSchema,
  progress: z.number(),
  logs: z.string().nullable().optional(),
  error_message: z.string().nullable().optional(),
  started_at: z.string().nullable().optional(),
  completed_at: z.string().nullable().optional(),
  created_at: z.string(),
});

export const EvaluationReportRecordSchema = z.object({
  id: z.string().uuid(),
  lesson_id: z.string().uuid(),
  report_json: z.record(z.unknown()),
  score_overall: z.number(),
  flags_json: z.array(z.unknown()).nullable().optional(),
  created_at: z.string(),
});

export const TopicInputSchema = z.object({
  topic: z.string(),
  domain: z.string().nullable().optional(),
  style_preset: z.string().nullable().optional(),
  target_duration_sec: z.number().int().nullable().optional(),
  music_enabled: z.boolean().default(true),
});

export const LessonCreateSchema = z.object({
  source_document_id: z.string().uuid().nullable().optional(),
  topic: z.string().nullable().optional(),
  domain: z.string().nullable().optional(),
  style_preset: z.string().nullable().optional(),
});

export const SceneUpdateSchema = z.object({
  narration_text: z.string().nullable().optional(),
  on_screen_text: z.array(z.string()).nullable().optional(),
  duration_sec: z.number().nullable().optional(),
});

export const SourceDocumentResponseSchema = SourceDocumentSchema;
export const SceneResponseSchema = SceneSchema;
export const LessonResponseSchema = LessonSchema;
export const LessonDetailResponseSchema = LessonResponseSchema.extend({
  scenes: z.array(SceneSchema),
});
export const LessonPlanResponseSchema = LessonPlanSchema;
export const SceneAssetResponseSchema = SceneAssetSchema;
export const EvaluationResponseSchema = EvaluationReportRecordSchema;
export const RenderJobResponseSchema = RenderJobSchema;

export const TranscriptSceneEntrySchema = z.object({
  scene_id: z.string().uuid(),
  text: z.string(),
  timestamp: z.number(),
});

export const TranscriptResponseSchema = z.object({
  full_text: z.string(),
  scenes: z.array(TranscriptSceneEntrySchema).default([]),
});

export const ProgressResponseSchema = z.object({
  stage: z.string(),
  progress: z.number(),
  message: z.string().default(''),
});

export type SourceDocumentType = z.infer<typeof SourceDocumentTypeSchema>;
export type SourceDocumentStatus = z.infer<typeof SourceDocumentStatusSchema>;
export type FragmentKind = z.infer<typeof FragmentKindSchema>;
export type LessonDomain = z.infer<typeof LessonDomainSchema>;
export type StylePreset = z.infer<typeof StylePresetSchema>;
export type LessonStatus = z.infer<typeof LessonStatusSchema>;
export type AssetType = z.infer<typeof AssetTypeSchema>;
export type AssetStatus = z.infer<typeof AssetStatusSchema>;
export type RenderJobStatus = z.infer<typeof RenderJobStatusSchema>;
export type Lesson = z.infer<typeof LessonSchema>;
export type SourceDocument = z.infer<typeof SourceDocumentSchema>;
export type SourceFragment = z.infer<typeof SourceFragmentSchema>;
export type LessonPlan = z.infer<typeof LessonPlanSchema>;
export type LessonPlanSection = z.infer<typeof LessonPlanSectionSchema>;
export type PlannedLesson = z.infer<typeof PlannedLessonSchema>;
export type SceneAsset = z.infer<typeof SceneAssetSchema>;
export type RenderJob = z.infer<typeof RenderJobSchema>;
export type EvaluationReportRecord = z.infer<typeof EvaluationReportRecordSchema>;
export type TopicInput = z.infer<typeof TopicInputSchema>;
export type LessonCreate = z.infer<typeof LessonCreateSchema>;
export type SceneUpdate = z.infer<typeof SceneUpdateSchema>;
export type LessonDetailResponse = z.infer<typeof LessonDetailResponseSchema>;
export type TranscriptSceneEntry = z.infer<typeof TranscriptSceneEntrySchema>;
export type TranscriptResponse = z.infer<typeof TranscriptResponseSchema>;
export type ProgressResponse = z.infer<typeof ProgressResponseSchema>;
