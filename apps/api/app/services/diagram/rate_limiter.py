"""Curated diagram spec and walkthrough states for Rate Limiter.

Produces a polished, professional system-design diagram with:
- Left-to-right architecture: Client -> Gateway -> Rate Limiter -> Redis -> App Servers
- Two clearly labeled flow paths (allowed / blocked)
- Side panel showing internal Rate Limiter logic
- Status badges inside the Rate Limiter component
- Example labels ("User A: 45/100 -> allowed")
- Algorithm overlay cards for fixed window, sliding window, token bucket, leaky bucket
"""

RATE_LIMITER_DIAGRAM_SPEC: dict = {
    "topic": "Rate Limiter",
    "layout": {
        "width": 1400,
        "height": 750,
        "direction": "left-to-right",
        "background": "#FAFBFC",
    },
    "components": [
        {
            "id": "client",
            "label": "Client / User",
            "x": 50,
            "y": 290,
            "w": 120,
            "h": 110,
            "icon": "user",
            "style": "rounded",
            "fill": "#FFFFFF",
            "stroke": "#B0BEC5",
        },
        {
            "id": "gateway",
            "label": "API Gateway /\nLoad Balancer",
            "x": 260,
            "y": 280,
            "w": 140,
            "h": 130,
            "icon": "gateway",
            "style": "rounded",
            "fill": "#F3E5F5",
            "stroke": "#7B1FA2",
        },
        {
            "id": "rate_limiter",
            "label": "Rate Limiter\nMiddleware",
            "x": 510,
            "y": 240,
            "w": 170,
            "h": 200,
            "icon": "shield",
            "style": "box",
            "fill": "#E3F2FD",
            "stroke": "#1565C0",
        },
        {
            "id": "redis",
            "label": "Redis / In-Memory\nCounter Store",
            "x": 790,
            "y": 280,
            "w": 150,
            "h": 130,
            "icon": "database",
            "style": "cylinder",
            "fill": "#FFF3E0",
            "stroke": "#E65100",
        },
        {
            "id": "app_servers",
            "label": "Application\nServers",
            "x": 1050,
            "y": 280,
            "w": 140,
            "h": 130,
            "icon": "server",
            "style": "rounded",
            "fill": "#E8F5E9",
            "stroke": "#2E7D32",
        },
    ],
    "connections": [
        {
            "id": "c1",
            "from": "client",
            "to": "gateway",
            "label": "HTTP Request",
            "path_group": "allowed",
        },
        {
            "id": "c2",
            "from": "gateway",
            "to": "rate_limiter",
            "label": "Forward with\nclient IP / API key",
        },
        {
            "id": "c3",
            "from": "rate_limiter",
            "to": "redis",
            "label": "GET / INCR\nrequest counter",
        },
        {
            "id": "c4",
            "from": "redis",
            "to": "app_servers",
            "label": "Allowed",
            "path_group": "allowed",
            "annotation": "200 OK",
            "annotation_color": "#2E7D32",
        },
        {
            "id": "c5",
            "from": "rate_limiter",
            "to": "client",
            "label": "429 Too Many Requests",
            "path_group": "blocked",
            "curve": "bottom",
        },
        {
            "id": "c6",
            "from": "redis",
            "to": "rate_limiter",
            "label": "counter value &\nTTL remaining",
            "curve": "top",
        },
    ],
    "annotations": [
        {
            "id": "a1",
            "text": "Fixed window / Sliding window\nalgorithm logic applied here",
            "anchor": "rate_limiter",
            "position": "top",
        },
        {
            "id": "a2",
            "text": "Window: 100 req / 60 sec\nper client key (IP or token)",
            "anchor": "redis",
            "position": "top",
        },
        {
            "id": "a3",
            "text": "Counter auto-expires\nwhen time window elapses",
            "anchor": "redis",
            "position": "bottom",
        },
    ],
    "flow_paths": {
        "allowed": {
            "color": "#43A047",
            "label": "Path A: Allowed Request Flow",
            "description": "User A: 45/100 \u2192 allowed",
        },
        "blocked": {
            "color": "#E53935",
            "label": "Path B: Blocked Request Flow",
            "description": "User A: 101/100 \u2192 blocked",
        },
    },
    "status_badges": [
        {
            "text": "count < limit\n\u2192 ALLOW",
            "color": "#43A047",
            "anchor": "rate_limiter",
            "position": "inner-top",
        },
        {
            "text": "count \u2265 limit\n\u2192 REJECT",
            "color": "#E53935",
            "anchor": "rate_limiter",
            "position": "inner-bottom",
        },
    ],
    "side_panel": {
        "title": "Rate Limiter Logic",
        "x": 1210,
        "y": 55,
        "w": 175,
        "items": [
            "1. Receive request",
            "2. Extract client key",
            "3. Read counter from store",
            "4. Increment counter",
            "5. Compare vs threshold",
            "6. Allow or reject",
            "7. TTL expires \u2192 reset",
        ],
    },
    "example_labels": [
        {"text": "User A: 45/100 \u2192 allowed", "color": "#43A047", "x": 50, "y": 720},
        {"text": "User A: 101/100 \u2192 blocked", "color": "#E53935", "x": 280, "y": 720},
        {"text": "Window: 100 req per 60s", "color": "#1565C0", "x": 510, "y": 720},
    ],
    "algorithm_overlays": {
        "fixed_window": {
            "label": "Fixed Window Counter",
            "description": "Divide time into fixed intervals (e.g. 60s); counter resets at each boundary.",
        },
        "sliding_window": {
            "label": "Sliding Window Log",
            "description": "Track each request timestamp; count within a rolling window for smoother limits.",
        },
        "token_bucket": {
            "label": "Token Bucket",
            "description": "Tokens added at a fixed rate; each request consumes one token. Allows short bursts.",
        },
        "leaky_bucket": {
            "label": "Leaky Bucket",
            "description": "Requests enqueue; processed at constant rate. Overflow is rejected immediately.",
        },
    },
}


RATE_LIMITER_WALKTHROUGH_STATES: list[dict] = [
    {
        "state_id": "overview",
        "title": "System Overview",
        "narration": (
            "A rate limiter sits between clients and your backend services. "
            "Its job is simple: count how many requests each user sends within "
            "a time window, and reject any that exceed the threshold. Let's walk "
            "through the full architecture."
        ),
        "focus_regions": [
            "client", "gateway", "rate_limiter", "redis", "app_servers",
        ],
        "highlight_paths": [],
        "dim_regions": [],
        "overlay_mode": None,
        "duration_sec": 15,
        "user_question_hooks": [
            "What happens when too many requests arrive?",
        ],
    },
    {
        "state_id": "allowed_flow",
        "title": "Allowed Request Path",
        "narration": (
            "When User A sends their 45th request out of a 100-request limit, "
            "the rate limiter checks the counter in Redis. The count is below the "
            "threshold, so the request passes through to the application servers, "
            "which respond with 200 OK."
        ),
        "focus_regions": [
            "client", "gateway", "rate_limiter", "redis", "app_servers",
        ],
        "highlight_paths": ["allowed"],
        "dim_regions": [],
        "overlay_mode": None,
        "duration_sec": 20,
        "user_question_hooks": [],
    },
    {
        "state_id": "blocked_flow",
        "title": "Blocked Request Path",
        "narration": (
            "But when User A sends request 101 \u2014 exceeding the 100-per-minute "
            "limit \u2014 the rate limiter immediately rejects it with a 429 Too Many "
            "Requests response. The request never reaches the backend servers, "
            "protecting them from overload."
        ),
        "focus_regions": ["client", "gateway", "rate_limiter"],
        "highlight_paths": ["blocked"],
        "dim_regions": ["redis", "app_servers"],
        "overlay_mode": None,
        "duration_sec": 20,
        "user_question_hooks": [
            "Why not let the application server decide to reject?",
        ],
    },
    {
        "state_id": "counter_mechanics",
        "title": "Counter & Window Mechanics",
        "narration": (
            "Redis stores a counter per client key \u2014 usually the user's IP or API token. "
            "Every incoming request increments this counter atomically using INCR. "
            "The key has a TTL equal to the window size, so the counter auto-expires "
            "and resets when the time window elapses. This is the core "
            "mechanism behind fixed-window rate limiting."
        ),
        "focus_regions": ["rate_limiter", "redis"],
        "highlight_paths": [],
        "dim_regions": ["client", "gateway", "app_servers"],
        "overlay_mode": None,
        "duration_sec": 22,
        "user_question_hooks": [
            "What's the difference between per-IP and per-user rate limiting?",
        ],
    },
    {
        "state_id": "fixed_window",
        "title": "Fixed Window Algorithm",
        "narration": (
            "In the fixed window approach, time is divided into non-overlapping intervals, "
            "like minute-long windows. A single counter tracks requests per window. "
            "The drawback: a burst at the boundary can allow 2x the limit across two windows."
        ),
        "focus_regions": ["rate_limiter"],
        "highlight_paths": [],
        "dim_regions": ["client", "gateway", "redis", "app_servers"],
        "overlay_mode": "fixed_window",
        "duration_sec": 20,
        "user_question_hooks": [
            "What happens at the boundary between two windows?",
        ],
    },
    {
        "state_id": "token_bucket",
        "title": "Token Bucket Algorithm",
        "narration": (
            "The token bucket is a popular alternative. Imagine a bucket that "
            "holds tokens \u2014 each request consumes one token. Tokens are refilled "
            "at a steady rate. If the bucket is empty, the request is rejected. "
            "This allows short bursts while enforcing an average rate."
        ),
        "focus_regions": ["rate_limiter"],
        "highlight_paths": [],
        "dim_regions": ["client", "gateway", "redis", "app_servers"],
        "overlay_mode": "token_bucket",
        "duration_sec": 25,
        "user_question_hooks": [
            "How does token bucket handle burst traffic differently from fixed window?",
        ],
    },
    {
        "state_id": "summary",
        "title": "Key Takeaways",
        "narration": (
            "To summarize: a rate limiter protects your API by counting requests "
            "per client within a time window. Allowed requests flow through to "
            "the backend; excess requests get a 429 response. You can choose "
            "between fixed window, sliding window, token bucket, or leaky bucket "
            "algorithms depending on your burst tolerance and precision needs."
        ),
        "focus_regions": [
            "client", "gateway", "rate_limiter", "redis", "app_servers",
        ],
        "highlight_paths": ["allowed", "blocked"],
        "dim_regions": [],
        "overlay_mode": None,
        "duration_sec": 20,
        "user_question_hooks": [],
    },
]


CURATED_TOPICS: dict[str, tuple[dict, list[dict]]] = {
    "rate_limiter": (RATE_LIMITER_DIAGRAM_SPEC, RATE_LIMITER_WALKTHROUGH_STATES),
    "rate limiter": (RATE_LIMITER_DIAGRAM_SPEC, RATE_LIMITER_WALKTHROUGH_STATES),
}


def get_curated_diagram(topic: str) -> tuple[dict, list[dict]] | None:
    """Return (diagram_spec, walkthrough_states) if a curated spec exists for *topic*."""
    key = topic.lower().strip().replace("-", "_").replace(" ", "_")
    result = CURATED_TOPICS.get(key)
    if result:
        return result
    for k, v in CURATED_TOPICS.items():
        if k in key or key in k:
            return v
    return None
