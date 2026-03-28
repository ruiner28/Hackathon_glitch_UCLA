export interface StyleBible {
  name: string;
  background: string;
  foreground: string;
  primary: string;
  secondary: string;
  accent: string;
  fontFamily: string;
  titleFontSize: number;
  bodyFontSize: number;
  lineColor: string;
  nodeColor: string;
  highlightColor: string;
  animationSpeed: 'slow' | 'normal' | 'fast';
}

export const STYLE_PRESETS: Record<string, StyleBible> = {
  clean_academic: {
    name: 'Clean Academic',
    background: '#FFFFFF',
    foreground: '#1E293B',
    primary: '#2563EB',
    secondary: '#0D9488',
    accent: '#F59E0B',
    fontFamily: 'Inter, system-ui, sans-serif',
    titleFontSize: 48,
    bodyFontSize: 24,
    lineColor: '#64748B',
    nodeColor: '#DBEAFE',
    highlightColor: '#2563EB',
    animationSpeed: 'normal',
  },
  modern_technical: {
    name: 'Modern Technical',
    background: '#0F172A',
    foreground: '#F8FAFC',
    primary: '#38BDF8',
    secondary: '#818CF8',
    accent: '#F472B6',
    fontFamily: 'JetBrains Mono, monospace',
    titleFontSize: 44,
    bodyFontSize: 22,
    lineColor: '#475569',
    nodeColor: '#1E3A5F',
    highlightColor: '#38BDF8',
    animationSpeed: 'normal',
  },
  cinematic_minimal: {
    name: 'Cinematic Minimal',
    background: '#18181B',
    foreground: '#FAFAFA',
    primary: '#A78BFA',
    secondary: '#34D399',
    accent: '#FB923C',
    fontFamily: 'Playfair Display, serif',
    titleFontSize: 52,
    bodyFontSize: 26,
    lineColor: '#52525B',
    nodeColor: '#27272A',
    highlightColor: '#A78BFA',
    animationSpeed: 'slow',
  },
};
