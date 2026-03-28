export interface CSRendererConfig {
  sceneType: string;
  requiredElements: string[];
  supportedAnimations: string[];
  defaultLayout: string;
  description: string;
}

export const CS_SCENE_CONFIGS: Record<string, CSRendererConfig> = {
  stack_animation: {
    sceneType: 'stack_animation',
    requiredElements: ['stack', 'input_tape', 'action_label'],
    supportedAnimations: ['stackPush', 'stackPop', 'highlightPulse'],
    defaultLayout: 'horizontal-split',
    description: 'Stack with push/pop animations, used for parser stack, call stack, etc.',
  },
  parse_tree_builder: {
    sceneType: 'parse_tree_builder',
    requiredElements: ['tree_canvas', 'node_labels', 'edge_lines'],
    supportedAnimations: ['nodeAppear', 'drawLine', 'highlightPulse'],
    defaultLayout: 'centered-tree',
    description: 'Animated tree construction showing parse tree or AST formation.',
  },
  dfa_nfa_transitions: {
    sceneType: 'dfa_nfa_transitions',
    requiredElements: ['state_circles', 'transition_arrows', 'input_indicator'],
    supportedAnimations: ['highlightPulse', 'arrowFlow', 'nodeAppear'],
    defaultLayout: 'graph-canvas',
    description: 'State machine diagram with animated transitions on input.',
  },
  recursion_tree: {
    sceneType: 'recursion_tree',
    requiredElements: ['tree_canvas', 'stack_frames', 'return_values'],
    supportedAnimations: ['nodeAppear', 'drawLine', 'fadeIn', 'stackPush', 'stackPop'],
    defaultLayout: 'tree-with-sidebar',
    description: 'Recursion call tree with corresponding stack frames.',
  },
  deadlock_graph: {
    sceneType: 'deadlock_graph',
    requiredElements: ['process_nodes', 'resource_nodes', 'request_edges', 'assignment_edges'],
    supportedAnimations: ['nodeAppear', 'drawLine', 'highlightPulse'],
    defaultLayout: 'bipartite-graph',
    description: 'Resource Allocation Graph with cycle detection highlighting.',
  },
  scheduling_timeline: {
    sceneType: 'scheduling_timeline',
    requiredElements: ['timeline_axis', 'process_bars', 'event_markers'],
    supportedAnimations: ['slideInLeft', 'highlightPulse', 'fadeIn'],
    defaultLayout: 'gantt-chart',
    description: 'Process scheduling Gantt chart with context switch markers.',
  },
  memory_layout: {
    sceneType: 'memory_layout',
    requiredElements: ['memory_blocks', 'pointer_arrows', 'labels'],
    supportedAnimations: ['fadeIn', 'highlightPulse', 'slideInUp'],
    defaultLayout: 'vertical-stack',
    description: 'Stack/heap/process memory layout visualization.',
  },
  sorting_visualizer: {
    sceneType: 'sorting_visualizer',
    requiredElements: ['bars', 'comparison_indicators', 'swap_animations'],
    supportedAnimations: ['highlightPulse', 'slideInUp'],
    defaultLayout: 'bar-chart',
    description: 'Array sorting visualization with comparison and swap animations.',
  },
  packet_flow: {
    sceneType: 'packet_flow',
    requiredElements: ['sender_node', 'receiver_node', 'packets', 'timeline'],
    supportedAnimations: ['arrowFlow', 'fadeIn', 'highlightPulse'],
    defaultLayout: 'sequence-diagram',
    description: 'Network packet flow between nodes with protocol state labels.',
  },
};
