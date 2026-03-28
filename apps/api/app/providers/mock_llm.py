import logging
import re
import uuid

from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Concept-graph databases keyed by normalised topic substring
# ---------------------------------------------------------------------------

_CONCEPT_GRAPHS: dict[str, dict] = {
    "bottom-up parsing": {
        "nodes": [
            {"id": "parsing", "label": "Parsing", "description": "Process of analysing a string of symbols conforming to a formal grammar.", "importance": 0.9, "prerequisites": []},
            {"id": "bottom_up", "label": "Bottom-Up Parsing", "description": "Parsing strategy that starts from the input tokens and works up to the start symbol by applying grammar productions in reverse.", "importance": 1.0, "prerequisites": ["parsing"]},
            {"id": "shift_reduce", "label": "Shift-Reduce Parsing", "description": "A class of bottom-up parsers that shift input onto a stack and reduce when a handle is found.", "importance": 0.95, "prerequisites": ["bottom_up"]},
            {"id": "lr_parser", "label": "LR Parser", "description": "Left-to-right, Rightmost-derivation parser. The most general and powerful class of shift-reduce parsers.", "importance": 0.95, "prerequisites": ["shift_reduce"]},
            {"id": "parse_table", "label": "Parse Table", "description": "Action-Goto table that drives an LR parser by mapping (state, symbol) pairs to shift/reduce/accept actions.", "importance": 0.85, "prerequisites": ["lr_parser"]},
            {"id": "derivation", "label": "Rightmost Derivation", "description": "Derivation where the rightmost non-terminal is replaced at each step. Bottom-up parsing discovers this in reverse.", "importance": 0.8, "prerequisites": ["parsing"]},
            {"id": "ast", "label": "Abstract Syntax Tree", "description": "Tree representation of the syntactic structure. The ultimate output of a parser.", "importance": 0.85, "prerequisites": ["derivation"]},
            {"id": "grammar", "label": "Context-Free Grammar", "description": "Set of recursive production rules used to describe the syntax of a language.", "importance": 0.9, "prerequisites": []},
            {"id": "handle", "label": "Handle", "description": "A substring that matches the right-hand side of a production and whose reduction moves the parse one step closer to the start symbol.", "importance": 0.8, "prerequisites": ["shift_reduce", "grammar"]},
            {"id": "reduce_action", "label": "Reduce Action", "description": "Parser action that replaces a handle on the stack with the corresponding non-terminal.", "importance": 0.75, "prerequisites": ["handle", "parse_table"]},
        ],
        "edges": [
            {"source": "parsing", "target": "bottom_up", "relation_type": "specialisation"},
            {"source": "bottom_up", "target": "shift_reduce", "relation_type": "implementation"},
            {"source": "shift_reduce", "target": "lr_parser", "relation_type": "specialisation"},
            {"source": "lr_parser", "target": "parse_table", "relation_type": "uses"},
            {"source": "parsing", "target": "derivation", "relation_type": "prerequisite"},
            {"source": "derivation", "target": "ast", "relation_type": "produces"},
            {"source": "grammar", "target": "handle", "relation_type": "defines"},
            {"source": "shift_reduce", "target": "handle", "relation_type": "identifies"},
            {"source": "handle", "target": "reduce_action", "relation_type": "triggers"},
            {"source": "parse_table", "target": "reduce_action", "relation_type": "encodes"},
            {"source": "grammar", "target": "parsing", "relation_type": "input_to"},
        ],
    },
    "deadlock": {
        "nodes": [
            {"id": "deadlock", "label": "Deadlock", "description": "A situation where two or more processes are permanently blocked, each waiting for a resource held by another.", "importance": 1.0, "prerequisites": []},
            {"id": "mutual_exclusion", "label": "Mutual Exclusion", "description": "At least one resource must be held in a non-shareable mode; only one process can use it at a time.", "importance": 0.9, "prerequisites": ["deadlock"]},
            {"id": "hold_and_wait", "label": "Hold and Wait", "description": "A process holds at least one resource while waiting to acquire additional resources held by other processes.", "importance": 0.9, "prerequisites": ["deadlock"]},
            {"id": "no_preemption", "label": "No Preemption", "description": "Resources cannot be forcibly taken from a process; they must be released voluntarily.", "importance": 0.9, "prerequisites": ["deadlock"]},
            {"id": "circular_wait", "label": "Circular Wait", "description": "There exists a circular chain of processes, each holding a resource needed by the next process in the chain.", "importance": 0.95, "prerequisites": ["deadlock"]},
            {"id": "rag", "label": "Resource Allocation Graph", "description": "Directed graph where vertices represent processes and resources, and edges represent requests and assignments.", "importance": 0.85, "prerequisites": ["deadlock"]},
            {"id": "prevention", "label": "Deadlock Prevention", "description": "Design protocols that ensure at least one of the four necessary conditions can never hold.", "importance": 0.85, "prerequisites": ["mutual_exclusion", "hold_and_wait", "no_preemption", "circular_wait"]},
            {"id": "avoidance", "label": "Deadlock Avoidance", "description": "Dynamically examine resource-allocation state to ensure the system never enters an unsafe state.", "importance": 0.85, "prerequisites": ["deadlock", "rag"]},
            {"id": "detection", "label": "Deadlock Detection", "description": "Allow deadlocks to occur, then detect and recover from them using algorithms on the wait-for graph.", "importance": 0.8, "prerequisites": ["rag"]},
            {"id": "bankers", "label": "Banker's Algorithm", "description": "Deadlock avoidance algorithm that simulates allocation to determine if a safe sequence exists before granting a request.", "importance": 0.9, "prerequisites": ["avoidance"]},
        ],
        "edges": [
            {"source": "deadlock", "target": "mutual_exclusion", "relation_type": "necessary_condition"},
            {"source": "deadlock", "target": "hold_and_wait", "relation_type": "necessary_condition"},
            {"source": "deadlock", "target": "no_preemption", "relation_type": "necessary_condition"},
            {"source": "deadlock", "target": "circular_wait", "relation_type": "necessary_condition"},
            {"source": "deadlock", "target": "rag", "relation_type": "modelled_by"},
            {"source": "mutual_exclusion", "target": "prevention", "relation_type": "addressed_by"},
            {"source": "hold_and_wait", "target": "prevention", "relation_type": "addressed_by"},
            {"source": "no_preemption", "target": "prevention", "relation_type": "addressed_by"},
            {"source": "circular_wait", "target": "prevention", "relation_type": "addressed_by"},
            {"source": "rag", "target": "detection", "relation_type": "enables"},
            {"source": "avoidance", "target": "bankers", "relation_type": "implemented_by"},
            {"source": "deadlock", "target": "avoidance", "relation_type": "strategy"},
            {"source": "deadlock", "target": "detection", "relation_type": "strategy"},
        ],
    },
    "rate limit": {
        "nodes": [
            {"id": "rate_limiting", "label": "Rate Limiting", "description": "Technique to control the rate of requests a client can make to a service in a given time window.", "importance": 1.0, "prerequisites": []},
            {"id": "token_bucket", "label": "Token Bucket", "description": "Algorithm where tokens are added to a bucket at a fixed rate; each request consumes a token. Allows short bursts.", "importance": 0.95, "prerequisites": ["rate_limiting"]},
            {"id": "leaky_bucket", "label": "Leaky Bucket", "description": "Algorithm that processes requests at a constant rate, smoothing out bursts like water leaking from a bucket.", "importance": 0.9, "prerequisites": ["rate_limiting"]},
            {"id": "sliding_window", "label": "Sliding Window", "description": "Tracks request counts in a sliding time window, combining the precision of fixed windows with smooth transitions.", "importance": 0.9, "prerequisites": ["rate_limiting"]},
            {"id": "distributed_rl", "label": "Distributed Rate Limiter", "description": "Rate limiting across multiple server instances using shared state in a distributed data store.", "importance": 0.85, "prerequisites": ["rate_limiting", "redis_counter"]},
            {"id": "api_gateway", "label": "API Gateway", "description": "Entry point that enforces rate limits before requests reach backend services.", "importance": 0.85, "prerequisites": ["rate_limiting"]},
            {"id": "redis_counter", "label": "Redis Counter", "description": "Using Redis INCR and EXPIRE commands to implement atomic, distributed request counters.", "importance": 0.8, "prerequisites": ["distributed_rl"]},
            {"id": "throttling", "label": "Request Throttling", "description": "Delaying or rejecting excess requests to protect services from overload.", "importance": 0.75, "prerequisites": ["rate_limiting"]},
        ],
        "edges": [
            {"source": "rate_limiting", "target": "token_bucket", "relation_type": "algorithm"},
            {"source": "rate_limiting", "target": "leaky_bucket", "relation_type": "algorithm"},
            {"source": "rate_limiting", "target": "sliding_window", "relation_type": "algorithm"},
            {"source": "rate_limiting", "target": "distributed_rl", "relation_type": "extension"},
            {"source": "rate_limiting", "target": "api_gateway", "relation_type": "enforced_at"},
            {"source": "distributed_rl", "target": "redis_counter", "relation_type": "implemented_by"},
            {"source": "rate_limiting", "target": "throttling", "relation_type": "outcome"},
            {"source": "token_bucket", "target": "distributed_rl", "relation_type": "combined_with"},
            {"source": "api_gateway", "target": "throttling", "relation_type": "performs"},
        ],
    },
}

# ---------------------------------------------------------------------------
# Lesson-plan databases
# ---------------------------------------------------------------------------

_LESSON_PLANS: dict[str, dict] = {
    "bottom-up parsing": {
        "lesson_title": "Compiler Bottom-Up Parsing",
        "target_audience": "undergraduate CS student",
        "estimated_duration_sec": 330,
        "objectives": [
            "Understand the motivation for bottom-up parsing over top-down approaches",
            "Trace through a shift-reduce parse of a simple expression",
            "Explain how LR parse tables drive the parsing process",
            "Construct a simple AST from a bottom-up parse",
        ],
        "prerequisites": ["Context-free grammars", "Derivations and parse trees", "Basic stack operations"],
        "misconceptions": [
            "Bottom-up parsing builds the tree from the root — it actually starts from the leaves",
            "LR parsers require backtracking — they are deterministic via the parse table",
            "Shift and reduce happen simultaneously — only one action occurs per step",
        ],
        "sections": [
            {
                "title": "Why Bottom-Up?",
                "objective": "Motivate bottom-up parsing by showing limitations of top-down recursive descent",
                "scene_type": "deterministic_animation",
                "duration_sec": 35,
                "key_points": ["Top-down struggles with left recursion", "Bottom-up defers decisions until more input is seen", "More grammars are LR than LL"],
                "visual_strategy": "Split-screen comparison: top-down tree growing down vs. bottom-up tree growing up with animated node placement",
            },
            {
                "title": "Shift-Reduce in Action",
                "objective": "Demonstrate the shift and reduce operations on a concrete example",
                "scene_type": "code_trace",
                "duration_sec": 45,
                "key_points": ["Stack holds partially parsed symbols", "Shift pushes the next token", "Reduce replaces a handle with a non-terminal"],
                "visual_strategy": "Animated stack with input tape: tokens slide from tape to stack, handle highlights in green, reduce pops and pushes non-terminal",
            },
            {
                "title": "Finding the Handle",
                "objective": "Explain what a handle is and how the parser identifies it",
                "scene_type": "deterministic_animation",
                "duration_sec": 35,
                "key_points": ["Handle = right side of a production at the top of the stack", "Reducing the handle corresponds to one step of rightmost derivation in reverse", "Incorrect handle choice leads to dead ends"],
                "visual_strategy": "Stack visualisation with candidate handle regions highlighted; correct handle pulses green",
            },
            {
                "title": "LR Parse Table",
                "objective": "Show how the Action-Goto table encodes shift/reduce decisions",
                "scene_type": "system_design_graph",
                "duration_sec": 40,
                "key_points": ["States represent viable prefixes", "Action table: shift/reduce/accept/error", "Goto table: transitions on non-terminals"],
                "visual_strategy": "Animated table with row/column highlighting as the parser steps through the input",
            },
            {
                "title": "Building the AST",
                "objective": "Show how reduce actions assemble the Abstract Syntax Tree",
                "scene_type": "deterministic_animation",
                "duration_sec": 40,
                "key_points": ["Each reduce creates a new AST node", "Children come from the popped stack symbols", "Final tree represents the program structure"],
                "visual_strategy": "Dual view: stack on the left shrinking, AST on the right growing with each reduce step",
            },
            {
                "title": "Worked Example: E → E + T | T, T → T * F | F, F → ( E ) | id",
                "objective": "Full trace of parsing id + id * id",
                "scene_type": "code_trace",
                "duration_sec": 45,
                "key_points": ["Walk through every shift and reduce", "Show parse table lookups", "Resulting AST respects operator precedence"],
                "visual_strategy": "Three-panel view: input tape, stack, and growing AST. Each step animates simultaneously.",
            },
            {
                "title": "LR Parser Variants",
                "objective": "Briefly compare SLR, LALR, and Canonical LR",
                "scene_type": "generated_still_with_motion",
                "duration_sec": 30,
                "key_points": ["SLR uses Follow sets — simplest but weakest", "LALR merges states with same core — used by yacc/Bison", "Canonical LR is most powerful but has largest tables"],
                "visual_strategy": "Venn diagram of grammar classes: SLR ⊂ LALR ⊂ LR(1), with parser tool logos on each ring",
            },
            {
                "title": "Recap & Key Takeaways",
                "objective": "Summarise the core ideas and connect them to real compiler tools",
                "scene_type": "summary_scene",
                "duration_sec": 25,
                "key_points": ["Bottom-up parsing constructs derivations in reverse", "LR parse tables make it deterministic", "Most production compilers use LALR parsers"],
                "visual_strategy": "Bullet-point fly-in animation with a miniature AST icon beside each point",
            },
        ],
    },
    "deadlock": {
        "lesson_title": "Deadlock in Operating Systems",
        "target_audience": "undergraduate CS student",
        "estimated_duration_sec": 360,
        "objectives": [
            "Define deadlock and identify the four necessary conditions",
            "Model resource allocation using a Resource Allocation Graph",
            "Compare prevention, avoidance, and detection strategies",
            "Trace the Banker's Algorithm on a concrete example",
        ],
        "prerequisites": ["Process and thread basics", "Mutual exclusion / critical sections", "Basic graph theory"],
        "misconceptions": [
            "Deadlock and starvation are the same thing — starvation is indefinite waiting, deadlock is permanent blocking",
            "Removing any one condition prevents deadlock — only if the remaining three can still co-exist",
            "The Banker's Algorithm prevents deadlock at zero cost — it has O(n²m) overhead per request",
        ],
        "sections": [
            {
                "title": "What is Deadlock?",
                "objective": "Define deadlock with the classic dining-philosophers analogy",
                "scene_type": "veo_cinematic",
                "duration_sec": 35,
                "key_points": ["Permanent blocking of a set of processes", "Each holds a resource another needs", "No process can proceed without external intervention"],
                "visual_strategy": "Cinematic overhead shot of five philosophers at a round table, chopsticks between them, two reaching for the same chopstick — freeze-frame",
            },
            {
                "title": "Four Necessary Conditions",
                "objective": "Introduce mutual exclusion, hold-and-wait, no preemption, and circular wait",
                "scene_type": "deterministic_animation",
                "duration_sec": 40,
                "key_points": ["All four must hold simultaneously", "Removing any one breaks the deadlock", "These are necessary but not sufficient on their own for all resource types"],
                "visual_strategy": "Four interlocking puzzle pieces, each labelled with a condition, assembling into a skull-and-crossbones deadlock icon",
            },
            {
                "title": "Resource Allocation Graph",
                "objective": "Model processes and resources as a directed graph to detect potential deadlocks",
                "scene_type": "system_design_graph",
                "duration_sec": 40,
                "key_points": ["Circles = processes, rectangles = resources with dots for instances", "Request edge: P → R, Assignment edge: R → P", "A cycle in the RAG may indicate deadlock"],
                "visual_strategy": "Interactive-style graph: nodes and edges animate in as each request/assignment is described",
            },
            {
                "title": "Deadlock Prevention",
                "objective": "Show how to structurally eliminate each of the four conditions",
                "scene_type": "deterministic_animation",
                "duration_sec": 40,
                "key_points": ["Eliminate hold-and-wait: request all resources at once", "Allow preemption: forcibly take resources", "Impose ordering to prevent circular wait"],
                "visual_strategy": "Four mini-animations, one per condition, each showing the prevention technique breaking the deadlock cycle",
            },
            {
                "title": "Deadlock Avoidance & the Banker's Algorithm",
                "objective": "Explain safe/unsafe states and trace the Banker's Algorithm",
                "scene_type": "code_trace",
                "duration_sec": 45,
                "key_points": ["Safe state: there exists at least one safe sequence", "Banker's simulates granting a request and checks safety", "If granting leads to unsafe state, process must wait"],
                "visual_strategy": "Table-based trace: Available, Max, Allocation, Need matrices animate row by row as the algorithm evaluates each process",
            },
            {
                "title": "Deadlock Detection & Recovery",
                "objective": "Describe detection algorithms and recovery options",
                "scene_type": "deterministic_animation",
                "duration_sec": 35,
                "key_points": ["Wait-for graph cycle detection", "Recovery: terminate processes or preempt resources", "Trade-offs: overhead of periodic detection vs. cost of deadlock"],
                "visual_strategy": "Animated wait-for graph with cycle highlighted in red; a 'recovery' action breaks an edge",
            },
            {
                "title": "Real-World Example: Database Transactions",
                "objective": "Show how databases handle deadlocks with lock ordering and timeouts",
                "scene_type": "generated_still_with_motion",
                "duration_sec": 30,
                "key_points": ["Databases use two-phase locking", "Deadlock detected via wait-for graph", "Victim transaction is rolled back"],
                "visual_strategy": "Two transaction timelines side by side with lock acquisition arrows, one marked as victim with rollback animation",
            },
            {
                "title": "Summary & Comparison",
                "objective": "Compare all strategies and when to use each",
                "scene_type": "summary_scene",
                "duration_sec": 25,
                "key_points": ["Prevention: restrictive but simple", "Avoidance: flexible but costly", "Detection: permissive but needs recovery mechanism"],
                "visual_strategy": "Comparison table with strategy rows and columns for overhead, flexibility, and complexity, animated cell-by-cell",
            },
        ],
    },
    "rate limit": {
        "lesson_title": "Rate Limiter System Design",
        "target_audience": "undergraduate CS student",
        "estimated_duration_sec": 320,
        "objectives": [
            "Explain why rate limiting is essential for API reliability",
            "Compare token-bucket, leaky-bucket, and sliding-window algorithms",
            "Design a distributed rate limiter using Redis",
            "Identify where to place rate limiting in a system architecture",
        ],
        "prerequisites": ["Basic HTTP and REST APIs", "Key-value stores (Redis basics)", "Distributed systems fundamentals"],
        "misconceptions": [
            "Rate limiting only prevents abuse — it also protects backend services from cascading failures",
            "Token bucket and leaky bucket are the same — token bucket allows bursts, leaky bucket enforces a steady rate",
            "Client-side rate limiting is sufficient — it can be bypassed; server-side is essential",
        ],
        "sections": [
            {
                "title": "Why Rate Limit?",
                "objective": "Motivate rate limiting with a traffic-spike scenario",
                "scene_type": "veo_cinematic",
                "duration_sec": 30,
                "key_points": ["Prevent service overload during traffic spikes", "Ensure fair usage among clients", "Protect against DDoS and abuse"],
                "visual_strategy": "Cinematic visualisation: a flood of request arrows overwhelming a server, then a shield (rate limiter) appearing and filtering them",
            },
            {
                "title": "Token Bucket Algorithm",
                "objective": "Explain token bucket mechanics with a visual simulation",
                "scene_type": "deterministic_animation",
                "duration_sec": 40,
                "key_points": ["Tokens added at fixed rate r", "Bucket has maximum capacity b", "Each request consumes one token; rejected if bucket empty", "Allows bursts up to bucket size"],
                "visual_strategy": "Animated bucket filling with green tokens at steady rate, requests arriving and consuming tokens, bucket depleting during burst",
            },
            {
                "title": "Leaky Bucket Algorithm",
                "objective": "Compare leaky bucket's constant-rate processing to token bucket",
                "scene_type": "deterministic_animation",
                "duration_sec": 35,
                "key_points": ["Requests enter a queue (bucket)", "Processed at constant rate regardless of arrival pattern", "Excess requests overflow and are dropped", "Smooths out bursts completely"],
                "visual_strategy": "Water-bucket metaphor: requests are water drops entering the bucket, water leaks out at constant rate through a hole at the bottom",
            },
            {
                "title": "Sliding Window Counter",
                "objective": "Show how sliding windows avoid the boundary problem of fixed windows",
                "scene_type": "code_trace",
                "duration_sec": 40,
                "key_points": ["Fixed window has boundary spike issue", "Sliding window log tracks every request timestamp", "Sliding window counter uses weighted previous + current window counts", "Trade-off: accuracy vs. memory"],
                "visual_strategy": "Timeline with two overlapping windows; request dots slide along and counters update in real time",
            },
            {
                "title": "Distributed Rate Limiting with Redis",
                "objective": "Design a distributed rate limiter using Redis atomic operations",
                "scene_type": "system_design_graph",
                "duration_sec": 45,
                "key_points": ["Multiple API servers share state via Redis", "INCR + EXPIRE for fixed-window counting", "Lua scripts for atomic sliding-window logic", "Race conditions and clock synchronisation"],
                "visual_strategy": "Architecture diagram: multiple API servers connected to Redis cluster, showing INCR/EXPIRE command flow with sequence numbers",
            },
            {
                "title": "Where to Place the Rate Limiter",
                "objective": "Discuss placement options: client, API gateway, middleware, service",
                "scene_type": "system_design_graph",
                "duration_sec": 30,
                "key_points": ["API Gateway: centralised, easy to manage", "Middleware: per-service granularity", "Client-side: cooperative but bypassable", "Multiple layers for defence in depth"],
                "visual_strategy": "Layered architecture diagram with rate-limiter badges at each layer, requests flowing through each checkpoint",
            },
            {
                "title": "Handling Throttled Requests",
                "objective": "Explain HTTP 429, Retry-After headers, and backoff strategies",
                "scene_type": "generated_still_with_motion",
                "duration_sec": 25,
                "key_points": ["Return HTTP 429 Too Many Requests", "Include Retry-After header", "Clients should implement exponential backoff", "Differentiate hard vs. soft limits"],
                "visual_strategy": "HTTP request/response exchange animation with 429 status code highlighted and a countdown timer for Retry-After",
            },
            {
                "title": "Recap & Design Checklist",
                "objective": "Summarise algorithms and provide a rate-limiter design checklist",
                "scene_type": "summary_scene",
                "duration_sec": 25,
                "key_points": ["Choose algorithm based on burst tolerance", "Use Redis for distributed state", "Place limiter at API gateway for simplicity", "Always return clear 429 responses with retry info"],
                "visual_strategy": "Checklist animation: items fly in with check marks, ending with a miniature architecture diagram",
            },
        ],
    },
}

# ---------------------------------------------------------------------------
# Scene-spec databases
# ---------------------------------------------------------------------------


def _build_scenes_for_plan(plan: dict, domain: str) -> list[dict]:
    """Build full SceneSpec dicts from a lesson-plan's sections."""
    scenes: list[dict] = []
    for idx, section in enumerate(plan.get("sections", [])):
        scene_type = section.get("scene_type", "deterministic_animation")

        # Select render strategy based on scene type
        render_strategy_map = {
            "deterministic_animation": "remotion",
            "generated_still_with_motion": "image_to_video",
            "veo_cinematic": "veo",
            "code_trace": "remotion",
            "system_design_graph": "remotion",
            "summary_scene": "remotion",
        }
        render_strategy = render_strategy_map.get(scene_type, "default")

        narration = _narration_for_section(section, plan.get("lesson_title", domain), idx)

        visual_elements = [
            {"type": "title_text", "description": section["title"], "position": "top-center", "style": "bold-32"},
        ]
        for kp in section.get("key_points", []):
            visual_elements.append(
                {"type": "bullet_point", "description": kp, "position": "center-left", "style": "regular-24"}
            )

        animation_beats = []
        duration = section.get("duration_sec", 30)
        beat_count = max(2, int(duration // 10))
        for b in range(beat_count):
            t = round(b * (duration / beat_count), 1)
            if b == 0:
                animation_beats.append({"timestamp_sec": t, "action": "fade_in", "description": f"Introduce {section['title']}"})
            elif b == beat_count - 1:
                animation_beats.append({"timestamp_sec": t, "action": "fade_out", "description": "Transition to next scene"})
            else:
                animation_beats.append({"timestamp_sec": t, "action": "reveal", "description": f"Reveal key point {b}"})

        asset_requests = []
        if scene_type in ("generated_still_with_motion", "veo_cinematic"):
            asset_requests.append({"type": "image", "prompt": section.get("visual_strategy", ""), "provider": "image"})
        if scene_type == "veo_cinematic":
            asset_requests.append({"type": "video", "prompt": section.get("visual_strategy", ""), "provider": "video"})

        mood_map = {
            "deterministic_animation": "focused",
            "code_trace": "focused",
            "system_design_graph": "neutral",
            "veo_cinematic": "dramatic",
            "generated_still_with_motion": "curious",
            "summary_scene": "uplifting",
        }

        scenes.append({
            "scene_id": str(uuid.uuid4()),
            "title": section["title"],
            "learning_objective": section.get("objective", ""),
            "source_refs": [],
            "scene_type": scene_type,
            "render_strategy": render_strategy,
            "duration_sec": duration,
            "narration_text": narration,
            "on_screen_text": section.get("key_points", []),
            "visual_elements": visual_elements,
            "animation_beats": animation_beats,
            "asset_requests": asset_requests,
            "veo_prompt": section.get("visual_strategy", "") if scene_type == "veo_cinematic" else None,
            "image_prompt": section.get("visual_strategy", "") if scene_type in ("generated_still_with_motion", "veo_cinematic") else None,
            "music_mood": mood_map.get(scene_type, "neutral"),
            "validation_notes": "",
        })
    return scenes


def _narration_for_section(section: dict, lesson_title: str, idx: int) -> str:
    """Generate pedagogically-clear narration text for a section."""
    title = section.get("title", "")
    objective = section.get("objective", "")
    key_points = section.get("key_points", [])

    if idx == 0:
        opening = f"Welcome to this lesson on {lesson_title}. Let's begin by exploring: {title.lower()}."
    else:
        opening = f"Now let's move on to {title.lower()}."

    body_parts = [f"Our goal here is to {objective.lower()}."] if objective else []
    for kp in key_points:
        body_parts.append(kp + ".")

    scene_type = section.get("scene_type", "")
    if scene_type == "summary_scene":
        closing = "Let's recap what we've learned."
    elif scene_type == "code_trace":
        closing = "Watch carefully as we trace through each step."
    else:
        closing = "Let's see how this works visually."

    return f"{opening} {' '.join(body_parts)} {closing}"


# ---------------------------------------------------------------------------
# Quiz databases
# ---------------------------------------------------------------------------

_QUIZZES: dict[str, list[dict]] = {
    "bottom-up parsing": [
        {
            "question": "In a shift-reduce parser, what does the 'shift' operation do?",
            "options": [
                "Replaces a handle on the stack with a non-terminal",
                "Pushes the next input token onto the parser stack",
                "Removes the top element from the stack",
                "Outputs the next symbol to the AST",
            ],
            "correct_answer": 1,
            "explanation": "The shift operation reads the next input token and pushes it onto the parser stack. The reduce operation is the one that replaces a handle with a non-terminal.",
        },
        {
            "question": "Which of the following is true about a 'handle' in bottom-up parsing?",
            "options": [
                "It is always the leftmost symbol on the stack",
                "It is a substring matching the RHS of a production, whose reduction represents one step of rightmost derivation in reverse",
                "It can only be a single terminal symbol",
                "It is identified by looking ahead at all remaining input",
            ],
            "correct_answer": 1,
            "explanation": "A handle is a substring on top of the stack that matches the right-hand side of some production, and reducing it corresponds to one step of the rightmost derivation performed in reverse.",
        },
        {
            "question": "What drives the decisions in an LR parser?",
            "options": [
                "A recursive descent function for each non-terminal",
                "A First/Follow set computed at runtime",
                "An Action-Goto parse table indexed by state and grammar symbol",
                "A priority queue of possible derivations",
            ],
            "correct_answer": 2,
            "explanation": "LR parsers use a precomputed Action-Goto table. The Action table tells the parser whether to shift, reduce, accept, or signal an error, while the Goto table handles transitions after a reduce.",
        },
        {
            "question": "Bottom-up parsing discovers which type of derivation?",
            "options": [
                "Leftmost derivation in forward order",
                "Rightmost derivation in reverse order",
                "Rightmost derivation in forward order",
                "A random derivation order",
            ],
            "correct_answer": 1,
            "explanation": "Bottom-up (shift-reduce) parsing effectively discovers the rightmost derivation, but in reverse — from the input string back up to the start symbol.",
        },
        {
            "question": "Which LR parser variant is used by tools like yacc and Bison?",
            "options": [
                "Canonical LR(1)",
                "SLR(1)",
                "LALR(1)",
                "LL(1)",
            ],
            "correct_answer": 2,
            "explanation": "LALR(1) — Look-Ahead LR(1) — merges states with the same core items, producing smaller tables than canonical LR while handling most practical grammars. yacc and Bison use LALR.",
        },
    ],
    "deadlock": [
        {
            "question": "Which of the following is NOT one of the four necessary conditions for deadlock?",
            "options": [
                "Mutual exclusion",
                "Hold and wait",
                "Bounded waiting",
                "Circular wait",
            ],
            "correct_answer": 2,
            "explanation": "The four necessary conditions are mutual exclusion, hold and wait, no preemption, and circular wait. Bounded waiting is a property related to synchronisation fairness, not deadlock.",
        },
        {
            "question": "In a Resource Allocation Graph, a cycle guarantees deadlock when:",
            "options": [
                "All resources have exactly one instance",
                "There are more processes than resources",
                "At least one resource is shareable",
                "The graph is bipartite",
            ],
            "correct_answer": 0,
            "explanation": "When every resource type has exactly one instance, a cycle in the RAG is both necessary and sufficient for deadlock. With multiple instances per resource type, a cycle is necessary but not sufficient.",
        },
        {
            "question": "The Banker's Algorithm is an example of:",
            "options": [
                "Deadlock prevention",
                "Deadlock detection",
                "Deadlock avoidance",
                "Deadlock recovery",
            ],
            "correct_answer": 2,
            "explanation": "The Banker's Algorithm is a deadlock avoidance strategy. It checks whether granting a resource request would leave the system in a safe state before proceeding.",
        },
        {
            "question": "What does it mean for a system to be in a 'safe state'?",
            "options": [
                "No process is currently waiting for a resource",
                "There exists at least one sequence in which all processes can complete",
                "All resources are currently available",
                "No cycles exist in the wait-for graph",
            ],
            "correct_answer": 1,
            "explanation": "A safe state means there exists at least one safe sequence — an ordering of all processes such that each can obtain its needed resources, finish, and release them for the next process.",
        },
    ],
    "rate limit": [
        {
            "question": "Which rate-limiting algorithm allows short bursts of traffic above the average rate?",
            "options": [
                "Leaky bucket",
                "Token bucket",
                "Fixed window counter",
                "Sliding window log",
            ],
            "correct_answer": 1,
            "explanation": "The token bucket algorithm allows bursts up to the bucket capacity. Tokens accumulate during idle periods, so a sudden burst can be served as long as sufficient tokens are available.",
        },
        {
            "question": "What HTTP status code should a rate limiter return when a request is throttled?",
            "options": [
                "403 Forbidden",
                "429 Too Many Requests",
                "503 Service Unavailable",
                "408 Request Timeout",
            ],
            "correct_answer": 1,
            "explanation": "HTTP 429 Too Many Requests is the standard status code indicating the client has exceeded the rate limit. It should include a Retry-After header telling the client when to retry.",
        },
        {
            "question": "Why is a distributed rate limiter more complex than a single-server one?",
            "options": [
                "It requires a more complex algorithm",
                "Multiple servers must share counter state, introducing synchronisation and consistency challenges",
                "It cannot use the token bucket algorithm",
                "HTTP 429 is not supported in distributed systems",
            ],
            "correct_answer": 1,
            "explanation": "In a distributed setting, multiple API servers need a shared data store (like Redis) to maintain consistent request counts. This introduces network latency, race conditions, and clock synchronisation challenges.",
        },
        {
            "question": "What is the main advantage of the sliding window counter over a fixed window counter?",
            "options": [
                "It uses less memory",
                "It avoids the boundary-spike problem where a burst at the window edge exceeds the intended limit",
                "It is easier to implement in Redis",
                "It does not require any counter state",
            ],
            "correct_answer": 1,
            "explanation": "Fixed window counters reset at window boundaries, allowing a burst of 2x the limit across the boundary. Sliding window counters weight the previous window's count, smoothing out this spike.",
        },
        {
            "question": "Which component is the most common place to enforce rate limiting in a microservices architecture?",
            "options": [
                "Each individual microservice",
                "The client application",
                "The API Gateway",
                "The database layer",
            ],
            "correct_answer": 2,
            "explanation": "The API Gateway is the most common enforcement point because it is the single entry point for all client requests, making it easy to apply rate limits centrally before requests fan out to microservices.",
        },
    ],
}


def _match_topic(text: str) -> str | None:
    """Find which mock topic best matches the input text."""
    normalised = text.lower()
    for key in _CONCEPT_GRAPHS:
        # Check for any keyword overlap
        keywords = key.split()
        if all(kw in normalised for kw in keywords):
            return key
    # Fallback heuristics
    if any(w in normalised for w in ("parser", "parsing", "compiler", "shift", "reduce", "lr")):
        return "bottom-up parsing"
    if any(w in normalised for w in ("deadlock", "banker", "mutex", "resource allocation")):
        return "deadlock"
    if any(w in normalised for w in ("rate", "limiter", "throttl", "token bucket", "leaky")):
        return "rate limit"
    return None


class MockLLMProvider(LLMProvider):
    """Mock LLM that returns rich, pre-built educational content for demo purposes."""

    async def extract_concepts(self, source_text: str, domain: str) -> dict:
        topic = _match_topic(source_text) or _match_topic(domain)
        if topic and topic in _CONCEPT_GRAPHS:
            logger.info("MockLLM: extract_concepts matched topic '%s'", topic)
            return _CONCEPT_GRAPHS[topic]

        # Generic fallback — build a small graph from the input text
        logger.info("MockLLM: extract_concepts using generic fallback for '%s'", domain)
        words = [w.strip(".,!?") for w in source_text.split() if len(w) > 3][:6]
        nodes = [
            {"id": f"concept_{i}", "label": w.title(), "description": f"Core concept: {w}", "importance": round(1.0 - i * 0.1, 2), "prerequisites": []}
            for i, w in enumerate(words)
        ]
        edges = [
            {"source": f"concept_{i}", "target": f"concept_{i + 1}", "relation_type": "related_to"}
            for i in range(len(words) - 1)
        ]
        return {"nodes": nodes, "edges": edges}

    async def create_lesson_plan(self, concepts: dict, domain: str, style: str) -> dict:
        topic = _match_topic(domain)
        if topic and topic in _LESSON_PLANS:
            logger.info("MockLLM: create_lesson_plan matched topic '%s'", topic)
            return _LESSON_PLANS[topic]

        # Generic fallback
        logger.info("MockLLM: create_lesson_plan using generic fallback for '%s'", domain)
        node_labels = [n.get("label", "Concept") for n in concepts.get("nodes", [])[:4]]
        sections = [
            {
                "title": "Introduction",
                "objective": f"Introduce the fundamentals of {domain}",
                "scene_type": "deterministic_animation",
                "duration_sec": 35,
                "key_points": [f"What is {domain}?", "Why does it matter?"],
                "visual_strategy": "Title card with animated text and domain icon",
            },
        ]
        for label in node_labels:
            sections.append({
                "title": label,
                "objective": f"Explain {label} in the context of {domain}",
                "scene_type": "deterministic_animation",
                "duration_sec": 35,
                "key_points": [f"Definition of {label}", f"Role of {label} in {domain}"],
                "visual_strategy": f"Diagram highlighting {label} and its relationships",
            })
        sections.append({
            "title": "Worked Example",
            "objective": f"Walk through a concrete example of {domain}",
            "scene_type": "code_trace",
            "duration_sec": 40,
            "key_points": ["Step-by-step trace", "Connect theory to practice"],
            "visual_strategy": "Code editor or diagram with step highlights",
        })
        sections.append({
            "title": "Summary",
            "objective": "Recap key takeaways",
            "scene_type": "summary_scene",
            "duration_sec": 25,
            "key_points": [f"Core ideas of {domain}", "Next steps for deeper learning"],
            "visual_strategy": "Bullet list fly-in with recap icons",
        })
        return {
            "lesson_title": domain,
            "target_audience": "undergraduate CS student",
            "estimated_duration_sec": sum(s["duration_sec"] for s in sections),
            "objectives": [f"Understand {domain}", f"Apply key concepts of {domain}"],
            "prerequisites": [],
            "misconceptions": [],
            "sections": sections,
        }

    async def compile_scenes(self, lesson_plan: dict, domain: str) -> list[dict]:
        logger.info("MockLLM: compile_scenes for '%s'", lesson_plan.get("lesson_title", domain))
        return _build_scenes_for_plan(lesson_plan, domain)

    async def write_narration(self, scene_spec: dict) -> str:
        title = scene_spec.get("title", "this topic")
        objective = scene_spec.get("learning_objective", "")
        key_points = scene_spec.get("on_screen_text", [])

        parts = [f"In this segment, we'll look at {title.lower()}."]
        if objective:
            parts.append(f"Our objective is to {objective.lower()}.")
        for kp in key_points:
            parts.append(kp + ".")
        parts.append("Let's continue to the next part of our lesson.")
        return " ".join(parts)

    async def generate_quiz(self, lesson_plan: dict, scenes: list[dict]) -> list[dict]:
        domain = lesson_plan.get("lesson_title", "")
        topic = _match_topic(domain)
        if topic and topic in _QUIZZES:
            logger.info("MockLLM: generate_quiz matched topic '%s'", topic)
            return _QUIZZES[topic]

        # Generic fallback
        logger.info("MockLLM: generate_quiz using generic fallback for '%s'", domain)
        return [
            {
                "question": f"What is the primary purpose of {domain}?",
                "options": [
                    f"To implement {domain} in hardware",
                    f"To understand and apply the core principles of {domain}",
                    f"To replace all existing approaches to {domain}",
                    f"To memorise definitions related to {domain}",
                ],
                "correct_answer": 1,
                "explanation": f"The primary purpose of studying {domain} is to understand and apply its core principles in practical scenarios.",
            },
            {
                "question": f"Which of the following best describes {domain}?",
                "options": [
                    "A hardware-level optimisation",
                    "A user-interface design pattern",
                    lesson_plan.get("objectives", ["A fundamental CS concept"])[0] if lesson_plan.get("objectives") else "A fundamental CS concept",
                    "An obsolete technique",
                ],
                "correct_answer": 2,
                "explanation": f"{domain} is best described by its primary learning objective.",
            },
            {
                "question": f"In the context of {domain}, which step typically comes first?",
                "options": [
                    "Evaluation",
                    "Implementation",
                    "Understanding the problem",
                    "Optimisation",
                ],
                "correct_answer": 2,
                "explanation": "Understanding the problem is always the first step before implementation or optimisation.",
            },
        ]

    async def evaluate_lesson(self, lesson_data: dict) -> dict:
        logger.info("MockLLM: evaluate_lesson")
        return {
            "overall_score": 0.87,
            "content_accuracy": {
                "score": 0.92,
                "feedback": "Content is technically accurate with correct definitions and relationships between concepts. All key terminology is used correctly.",
            },
            "pedagogical_quality": {
                "score": 0.88,
                "feedback": "Good scaffolding from simple to complex ideas. The worked example effectively bridges theory and practice. Consider adding one more intermediate example.",
            },
            "visual_quality": {
                "score": 0.82,
                "feedback": "Visual strategies are well-chosen for each scene type. The animations support understanding rather than distracting. Dual-view panels are particularly effective.",
            },
            "narration_quality": {
                "score": 0.85,
                "feedback": "Narration is clear and maintains an appropriate pace. Transitions between scenes are smooth. Some sentences could be shortened for better retention.",
            },
            "engagement": {
                "score": 0.80,
                "feedback": "Good variety of scene types keeps attention. The cinematic opening is engaging. The quiz questions test understanding rather than recall.",
            },
            "flags": [],
            "suggestions": [
                "Consider adding a brief 'common mistakes' scene before the summary",
                "The worked-example scene could benefit from a pause-and-predict moment",
                "Adding timestamps or progress indicators would help learners navigate",
            ],
        }
