export interface SystemDesignRendererConfig {
  sceneType: string;
  requiredElements: string[];
  supportedAnimations: string[];
  defaultLayout: string;
  description: string;
}

export const SYSTEM_DESIGN_SCENE_CONFIGS: Record<string, SystemDesignRendererConfig> = {
  request_flow: {
    sceneType: 'request_flow',
    requiredElements: ['client', 'api_gateway', 'services', 'arrows'],
    supportedAnimations: ['arrowFlow', 'highlightPulse', 'nodeAppear'],
    defaultLayout: 'left-to-right-flow',
    description: 'End-to-end request flow through microservices.',
  },
  load_balancer: {
    sceneType: 'load_balancer',
    requiredElements: ['lb_node', 'server_nodes', 'request_arrows', 'distribution_labels'],
    supportedAnimations: ['arrowFlow', 'highlightPulse', 'counterIncrement'],
    defaultLayout: 'fan-out',
    description: 'Load balancer distributing requests across server instances.',
  },
  cache_flow: {
    sceneType: 'cache_flow',
    requiredElements: ['client', 'cache', 'database', 'hit_path', 'miss_path'],
    supportedAnimations: ['arrowFlow', 'highlightPulse', 'fadeIn'],
    defaultLayout: 'decision-flow',
    description: 'Cache hit/miss flow with decision branching.',
  },
  token_bucket: {
    sceneType: 'token_bucket',
    requiredElements: ['bucket', 'tokens', 'request_stream', 'refill_indicator'],
    supportedAnimations: ['fadeIn', 'scaleIn', 'counterIncrement', 'popIn'],
    defaultLayout: 'centered-with-sidebar',
    description: 'Token bucket rate limiter visualization.',
  },
  pub_sub: {
    sceneType: 'pub_sub',
    requiredElements: ['publishers', 'topic', 'subscribers', 'message_arrows'],
    supportedAnimations: ['arrowFlow', 'nodeAppear', 'fadeIn'],
    defaultLayout: 'fan-in-fan-out',
    description: 'Pub-sub message distribution pattern.',
  },
  database_replication: {
    sceneType: 'database_replication',
    requiredElements: ['primary_db', 'replica_dbs', 'replication_arrows', 'write_path', 'read_path'],
    supportedAnimations: ['arrowFlow', 'highlightPulse', 'fadeIn'],
    defaultLayout: 'primary-replica',
    description: 'Database primary-replica replication flow.',
  },
  architecture_diagram: {
    sceneType: 'architecture_diagram',
    requiredElements: ['service_nodes', 'connections', 'labels', 'zones'],
    supportedAnimations: ['nodeAppear', 'drawLine', 'fadeIn'],
    defaultLayout: 'layered-architecture',
    description: 'Full system architecture with service nodes and connections.',
  },
  queue_consumers: {
    sceneType: 'queue_consumers',
    requiredElements: ['producers', 'queue', 'consumers', 'message_items'],
    supportedAnimations: ['slideInLeft', 'slideInRight', 'fadeIn', 'counterIncrement'],
    defaultLayout: 'pipeline',
    description: 'Message queue with producers and consumers.',
  },
};
