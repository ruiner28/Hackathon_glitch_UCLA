export interface ProviderConfig {
  provider: string;
  mode: 'mock' | 'google';
  apiKey?: string;
  projectId?: string;
}

export interface GenerationResult {
  success: boolean;
  url?: string;
  error?: string;
  metadata?: Record<string, unknown>;
}

// TODO: Implement TypeScript provider clients for frontend-side integrations
export const PROVIDER_DEFAULTS: Record<string, ProviderConfig> = {
  llm: { provider: 'gemini', mode: 'mock' },
  image: { provider: 'imagen', mode: 'mock' },
  video: { provider: 'veo', mode: 'mock' },
  tts: { provider: 'google-tts', mode: 'mock' },
  music: { provider: 'lyria', mode: 'mock' },
};
