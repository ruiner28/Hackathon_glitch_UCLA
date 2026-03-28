export interface AnimationPreset {
  name: string;
  duration: number;
  easing: string;
  delay?: number;
}

export const ANIMATION_PRESETS: Record<string, AnimationPreset> = {
  fadeIn: { name: 'fadeIn', duration: 500, easing: 'ease-out' },
  fadeOut: { name: 'fadeOut', duration: 400, easing: 'ease-in' },
  slideInLeft: { name: 'slideInLeft', duration: 600, easing: 'ease-out' },
  slideInRight: { name: 'slideInRight', duration: 600, easing: 'ease-out' },
  slideInUp: { name: 'slideInUp', duration: 500, easing: 'ease-out' },
  scaleIn: { name: 'scaleIn', duration: 400, easing: 'ease-out' },
  popIn: { name: 'popIn', duration: 300, easing: 'cubic-bezier(0.34, 1.56, 0.64, 1)' },
  highlightPulse: { name: 'highlightPulse', duration: 800, easing: 'ease-in-out' },
  drawLine: { name: 'drawLine', duration: 1000, easing: 'ease-in-out' },
  nodeAppear: { name: 'nodeAppear', duration: 500, easing: 'ease-out', delay: 100 },
  arrowFlow: { name: 'arrowFlow', duration: 800, easing: 'linear' },
  stackPush: { name: 'stackPush', duration: 400, easing: 'ease-out' },
  stackPop: { name: 'stackPop', duration: 350, easing: 'ease-in' },
  counterIncrement: { name: 'counterIncrement', duration: 200, easing: 'ease-out' },
};
