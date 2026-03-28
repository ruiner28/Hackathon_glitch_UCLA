import { z } from 'zod';

export const CategoryScoreSchema = z.object({
  score: z.number().default(0),
  feedback: z.string().default(''),
});

export const EvaluationReportSchema = z.object({
  overall_score: z.number().default(0),
  content_accuracy: CategoryScoreSchema.default({ score: 0, feedback: '' }),
  pedagogical_quality: CategoryScoreSchema.default({ score: 0, feedback: '' }),
  visual_quality: CategoryScoreSchema.default({ score: 0, feedback: '' }),
  narration_quality: CategoryScoreSchema.default({ score: 0, feedback: '' }),
  engagement: CategoryScoreSchema.default({ score: 0, feedback: '' }),
  flags: z.array(z.string()).default([]),
  suggestions: z.array(z.string()).default([]),
});

export type CategoryScore = z.infer<typeof CategoryScoreSchema>;
export type EvaluationReport = z.infer<typeof EvaluationReportSchema>;
