import { z } from 'zod';

export const ConceptNodeSchema = z.object({
  id: z.string(),
  label: z.string(),
  description: z.string(),
  importance: z.number().min(0).max(1),
  prerequisites: z.array(z.string()),
});

export const ConceptEdgeSchema = z.object({
  source: z.string(),
  target: z.string(),
  relation_type: z.string(),
});

export const ConceptGraphSchema = z.object({
  nodes: z.array(ConceptNodeSchema),
  edges: z.array(ConceptEdgeSchema),
});

export type ConceptNode = z.infer<typeof ConceptNodeSchema>;
export type ConceptEdge = z.infer<typeof ConceptEdgeSchema>;
export type ConceptGraph = z.infer<typeof ConceptGraphSchema>;
