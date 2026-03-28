import { z } from 'zod';

export const QuizQuestionSchema = z.object({
  question: z.string(),
  options: z.array(z.string()).min(2).max(6),
  correct_index: z.number().int().min(0),
  explanation: z.string(),
});

export const QuizResponseSchema = z.object({
  questions: z.array(QuizQuestionSchema),
});

export type QuizQuestion = z.infer<typeof QuizQuestionSchema>;
export type QuizResponse = z.infer<typeof QuizResponseSchema>;
