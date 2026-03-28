import { z } from 'zod';

export const SceneTypeSchema = z.enum([
  'deterministic_animation',
  'generated_still_with_motion',
  'veo_cinematic',
  'code_trace',
  'system_design_graph',
  'summary_scene',
]);

export const SceneStatusSchema = z.enum(['pending', 'generating', 'rendered', 'error']);

export const VisualElementSchema = z.object({
  type: z.string().default(''),
  description: z.string().default(''),
  position: z.string().default(''),
  style: z.string().default(''),
});

export const AnimationBeatSchema = z.object({
  timestamp_sec: z.number().default(0),
  action: z.string().default(''),
  description: z.string().default(''),
});

export const AssetRequestSchema = z.object({
  type: z.string().default(''),
  prompt: z.string().default(''),
  provider: z.string().default(''),
});

export const SceneSpecSchema = z.object({
  scene_id: z.string().default(''),
  title: z.string().default(''),
  learning_objective: z.string().default(''),
  source_refs: z.array(z.string()).default([]),
  scene_type: z.string().default('deterministic_animation'),
  render_strategy: z.string().default('default'),
  duration_sec: z.number().default(30),
  narration_text: z.string().default(''),
  on_screen_text: z.array(z.string()).default([]),
  visual_elements: z.array(VisualElementSchema).default([]),
  animation_beats: z.array(AnimationBeatSchema).default([]),
  asset_requests: z.array(AssetRequestSchema).default([]),
  veo_prompt: z.string().nullable().optional(),
  image_prompt: z.string().nullable().optional(),
  music_mood: z.string().default('neutral'),
  validation_notes: z.string().default(''),
});

export const SceneSchema = z.object({
  id: z.string().uuid(),
  lesson_id: z.string().uuid(),
  scene_order: z.number().int(),
  scene_type: SceneTypeSchema,
  title: z.string(),
  duration_sec: z.number(),
  render_strategy: z.string(),
  source_refs_json: z.array(z.unknown()).nullable().optional(),
  narration_text: z.string().nullable().optional(),
  on_screen_text_json: z.union([z.array(z.unknown()), z.record(z.unknown())]).nullable().optional(),
  scene_spec_json: SceneSpecSchema.nullable().optional(),
  status: SceneStatusSchema,
  created_at: z.string(),
  updated_at: z.string().nullable().optional(),
});

export type SceneType = z.infer<typeof SceneTypeSchema>;
export type SceneStatus = z.infer<typeof SceneStatusSchema>;
export type VisualElement = z.infer<typeof VisualElementSchema>;
export type AnimationBeat = z.infer<typeof AnimationBeatSchema>;
export type AssetRequest = z.infer<typeof AssetRequestSchema>;
export type SceneSpec = z.infer<typeof SceneSpecSchema>;
export type Scene = z.infer<typeof SceneSchema>;
