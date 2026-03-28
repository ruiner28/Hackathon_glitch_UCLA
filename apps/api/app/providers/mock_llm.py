import logging
import re
import uuid

from app.providers.base import LLMProvider
from app.services.visual_system import (
    VEO_DURATION_MAX,
    build_nano_banana_prompt,
    build_veo_prompt,
    pick_veo_duration_sec,
    score_veo_eligibility,
)
from app.services.visual_system.style_presets import VISUAL_IDENTITY_TOKEN

logger = logging.getLogger(__name__)

CONTINUITY_MOTIF_RATE_LIMIT = "teal gateway orb filtering amber request particles"

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
                "scene_type": "veo_cinematic",
                "duration_sec": 35,
                "key_points": [
                    "Top-down fails on left recursion",
                    "Bottom-up defers decisions",
                    "LR handles more grammars than LL",
                ],
                "narration": (
                    "When a compiler reads your source code, it needs to understand its structure — and that "
                    "process is called parsing. Top-down parsers like recursive descent are intuitive, but they "
                    "struggle with left-recursive grammars and often need special rewriting. Bottom-up parsing "
                    "takes the opposite approach: instead of guessing which rule to apply from the top, it reads "
                    "input tokens and works upward, deferring decisions until it has enough context. This makes "
                    "it far more powerful — in fact, more grammars are LR-parseable than LL-parseable. In this "
                    "lesson, we'll trace through the mechanics of bottom-up parsing step by step."
                ),
                "visual_strategy": "Split-screen: top-down tree vs bottom-up tree growing in opposite directions",
            },
            {
                "title": "Shift-Reduce in Action",
                "objective": "Demonstrate the shift and reduce operations on a concrete example",
                "scene_type": "code_trace",
                "duration_sec": 45,
                "key_points": [
                    "Stack ← partially parsed symbols",
                    "Shift → push next input token",
                    "Reduce → replace handle with NT",
                    "Repeat until start symbol",
                ],
                "narration": (
                    "The core engine of bottom-up parsing is the shift-reduce loop. The parser maintains a stack "
                    "of symbols and reads from an input tape. At each step, it makes one of two decisions. A shift "
                    "moves the next input token onto the stack. A reduce recognizes that the top of the stack "
                    "matches the right-hand side of a grammar production — called a handle — and replaces it "
                    "with the corresponding non-terminal. This process continues until the entire input has been "
                    "consumed and the stack contains only the start symbol, meaning the input was valid."
                ),
                "visual_strategy": "Animated stack with input tape showing shift and reduce operations",
            },
            {
                "title": "Finding the Handle",
                "objective": "Explain what a handle is and how the parser identifies it",
                "scene_type": "deterministic_animation",
                "duration_sec": 35,
                "key_points": [
                    "Handle = RHS at stack top",
                    "Matches a production rule",
                    "Reverse of rightmost derivation",
                    "Wrong handle → dead end",
                ],
                "narration": (
                    "The critical challenge in shift-reduce parsing is identifying the handle — the substring "
                    "at the top of the stack that should be reduced. A handle matches the right-hand side of "
                    "some production, and reducing it corresponds to one step of the rightmost derivation in "
                    "reverse. Choosing the wrong handle leads to a dead end, where no further reductions are "
                    "possible. This is exactly why we need a systematic method — the LR parse table — to make "
                    "this decision deterministically at every step."
                ),
                "visual_strategy": "Stack with candidate handle regions highlighted, correct one pulses green",
            },
            {
                "title": "LR Parse Table",
                "objective": "Show how the Action-Goto table encodes shift/reduce decisions",
                "scene_type": "system_design_graph",
                "duration_sec": 40,
                "key_points": [
                    "States = viable prefixes",
                    "Action: shift / reduce / accept",
                    "Goto: non-terminal transitions",
                    "(state, symbol) → decision",
                ],
                "narration": (
                    "Instead of guessing which action to take, an LR parser uses a precomputed table. The table "
                    "has two parts. The Action table maps a pair of current state and input terminal to a "
                    "decision: shift to a new state, reduce by a specific production, accept the input, or "
                    "report an error. The Goto table handles non-terminals — after a reduce creates a "
                    "non-terminal, the Goto table tells the parser which state to transition to. Together, "
                    "these tables make the parser completely deterministic and very fast."
                ),
                "visual_strategy": "Table with row/column highlighting as parser steps through input",
            },
            {
                "title": "Building the AST",
                "objective": "Show how reduce actions assemble the Abstract Syntax Tree",
                "scene_type": "deterministic_animation",
                "duration_sec": 40,
                "key_points": [
                    "Each reduce → new AST node",
                    "Children from popped symbols",
                    "Tree grows from leaves up",
                    "Final tree = program structure",
                ],
                "narration": (
                    "As the parser performs each reduce action, it's not just transforming the stack — it's "
                    "building the Abstract Syntax Tree. Every time symbols are popped off the stack and replaced "
                    "by a non-terminal, a new AST node is created with those popped symbols as its children. "
                    "Because bottom-up parsing starts from the input tokens and works toward the start symbol, "
                    "the AST grows from the leaves upward. By the time the parser accepts, the complete tree "
                    "captures the entire hierarchical structure of the program."
                ),
                "visual_strategy": "Dual view: stack on left shrinking, AST on right growing with each reduce",
            },
            {
                "title": "Worked Example: id + id * id",
                "objective": "Full trace of parsing id + id * id using a concrete grammar",
                "scene_type": "code_trace",
                "duration_sec": 45,
                "key_points": [
                    "E → E+T | T",
                    "T → T*F | F",
                    "F → (E) | id",
                    "AST respects precedence",
                ],
                "narration": (
                    "Let's trace a complete example. Given the grammar E produces E plus T or T, T produces "
                    "T times F or F, and F produces parenthesized E or id, let's parse the expression "
                    "id plus id times id. The parser begins by shifting id, then reduces F to id, then T to F, "
                    "then E to T. It shifts plus, then id, reduces again through F and T. Then it shifts times "
                    "and id, reduces F, then T times F to T. Finally E plus T reduces to E, and the parser "
                    "accepts. Notice that the resulting AST naturally respects operator precedence — "
                    "multiplication is deeper in the tree than addition."
                ),
                "visual_strategy": "Three-panel: input tape, stack, and growing AST animated step by step",
            },
            {
                "title": "LR Parser Variants",
                "objective": "Briefly compare SLR, LALR, and Canonical LR",
                "scene_type": "generated_still_with_motion",
                "duration_sec": 30,
                "key_points": [
                    "SLR: Follow sets (simplest)",
                    "LALR: merged states (yacc/Bison)",
                    "CLR: full power, large tables",
                    "SLR ⊂ LALR ⊂ LR(1)",
                ],
                "narration": (
                    "Not all LR parsers are created equal. SLR is the simplest — it uses Follow sets to resolve "
                    "conflicts but can't handle all LR grammars. LALR improves on this by merging states that "
                    "share the same core items, and it's what tools like yacc and Bison actually use. Canonical "
                    "LR is the most powerful variant, able to handle any LR(1) grammar, but at the cost of "
                    "much larger parse tables. In practice, LALR hits the sweet spot between power and "
                    "table size, which is why it dominates in real compiler construction."
                ),
                "visual_strategy": "Nested diagram of grammar classes: SLR ⊂ LALR ⊂ LR(1)",
            },
            {
                "title": "Recap & Key Takeaways",
                "objective": "Summarise the core ideas and connect them to real compiler tools",
                "scene_type": "summary_scene",
                "duration_sec": 25,
                "key_points": [
                    "Bottom-up → reverse derivation",
                    "Shift-reduce → stack + input",
                    "Handle → correct reduction",
                    "Parse table → deterministic",
                    "LALR → practical sweet spot",
                ],
                "narration": (
                    "Let's recap. Bottom-up parsing works by discovering the rightmost derivation in reverse, "
                    "building the syntax tree from the leaves up. The shift-reduce mechanism uses a stack and "
                    "input tape, with the critical challenge being handle identification. LR parse tables solve "
                    "this deterministically by precomputing every decision. Among the variants, LALR parsers "
                    "offer the best balance of power and efficiency, and they're the foundation of tools "
                    "like yacc, Bison, and many modern parser generators. Understanding this machinery gives "
                    "you insight into how every compiler turns source code into executable programs."
                ),
                "visual_strategy": "Checklist with miniature AST icons beside each point",
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
                "key_points": [
                    "Permanent blocking of processes",
                    "Each holds what another needs",
                    "No progress without intervention",
                ],
                "narration": (
                    "Imagine two cars approaching a single-lane bridge from opposite sides at the same time. "
                    "Neither can move forward, and neither is willing to back up. That's deadlock — a permanent "
                    "state where a set of processes are blocked, each holding a resource that another process "
                    "needs, with no process able to make progress. In operating systems, deadlock can freeze "
                    "entire applications. Understanding how it forms and how to prevent it is fundamental to "
                    "building reliable concurrent systems. In this lesson, we'll dissect the four conditions "
                    "that cause deadlock and explore three strategies to deal with it."
                ),
                "visual_strategy": "Cinematic: five philosophers at a round table, each reaching for chopsticks — freeze-frame",
            },
            {
                "title": "Four Necessary Conditions",
                "objective": "Introduce mutual exclusion, hold-and-wait, no preemption, and circular wait",
                "scene_type": "deterministic_animation",
                "duration_sec": 40,
                "key_points": [
                    "1. Mutual exclusion",
                    "2. Hold and wait",
                    "3. No preemption",
                    "4. Circular wait",
                    "All four must hold simultaneously",
                ],
                "narration": (
                    "Deadlock requires exactly four conditions to hold at the same time. First, mutual "
                    "exclusion — at least one resource can only be used by one process at a time. Second, hold "
                    "and wait — a process holds one resource while waiting to acquire another. Third, no "
                    "preemption — resources cannot be forcibly taken from a process. And fourth, circular wait — "
                    "there's a circular chain where each process waits for a resource held by the next. "
                    "These are called the Coffman conditions. If even one is absent, deadlock cannot occur, "
                    "and that's the key insight behind every prevention strategy."
                ),
                "visual_strategy": "Four interlocking puzzle pieces labelled with conditions, assembling into deadlock icon",
            },
            {
                "title": "Resource Allocation Graph",
                "objective": "Model processes and resources as a directed graph to detect potential deadlocks",
                "scene_type": "system_design_graph",
                "duration_sec": 40,
                "key_points": [
                    "○ = process nodes",
                    "□ = resource nodes (with dots)",
                    "P → R = request edge",
                    "R → P = assignment edge",
                    "Cycle → possible deadlock",
                ],
                "narration": (
                    "To analyze deadlock systematically, we use a Resource Allocation Graph. Processes are "
                    "shown as circles, and resources as rectangles with dots representing individual instances. "
                    "A request edge goes from a process to a resource it's waiting for. An assignment edge goes "
                    "from a resource instance to the process holding it. The critical insight: if this graph "
                    "contains a cycle, deadlock may be present. For single-instance resources, a cycle "
                    "guarantees deadlock. For multi-instance resources, a cycle is necessary but not "
                    "sufficient — we need additional analysis."
                ),
                "visual_strategy": "Graph with process circles and resource rectangles, edges animating in with request/assignment flow",
            },
            {
                "title": "Deadlock Prevention",
                "objective": "Show how to structurally eliminate each of the four conditions",
                "scene_type": "deterministic_animation",
                "duration_sec": 40,
                "key_points": [
                    "Break hold-and-wait → request all at once",
                    "Allow preemption → force release",
                    "Order resources → prevent circular wait",
                    "Trade-off: restrictive but guaranteed",
                ],
                "narration": (
                    "Prevention works by structurally ensuring that at least one of the four Coffman conditions "
                    "can never hold. To eliminate hold-and-wait, require processes to request all resources at "
                    "once before starting — but this wastes resources that sit idle. To allow preemption, "
                    "forcibly take resources from waiting processes — but this risks data corruption. The "
                    "most practical technique is imposing a total ordering on resources: if every process "
                    "must acquire resources in the same numbered order, circular wait becomes impossible. "
                    "Prevention is restrictive but provides absolute guarantees."
                ),
                "visual_strategy": "Four mini-diagrams showing each prevention technique breaking the deadlock cycle",
            },
            {
                "title": "Banker's Algorithm",
                "objective": "Explain safe/unsafe states and trace the Banker's Algorithm",
                "scene_type": "code_trace",
                "duration_sec": 45,
                "key_points": [
                    "Safe state → safe sequence exists",
                    "Need = Max - Allocation",
                    "Simulate: can process finish?",
                    "Unsafe → deny the request",
                ],
                "narration": (
                    "Instead of preventing deadlock outright, avoidance takes a smarter approach — it allows "
                    "resource allocation but checks each request to ensure the system stays in a safe state. "
                    "A safe state is one where there exists at least one sequence in which every process can "
                    "finish. The Banker's Algorithm, proposed by Dijkstra, performs this check. For each "
                    "process, it computes the Need matrix — the difference between maximum demand and current "
                    "allocation. It then simulates granting the request: if the remaining available resources "
                    "can satisfy at least one process's needs, that process can finish and release its "
                    "resources, potentially enabling others. If no safe sequence exists, the request is denied."
                ),
                "visual_strategy": "Table trace: Available, Max, Allocation, Need matrices with row-by-row evaluation",
            },
            {
                "title": "Detection & Recovery",
                "objective": "Describe detection algorithms and recovery options",
                "scene_type": "deterministic_animation",
                "duration_sec": 35,
                "key_points": [
                    "Wait-for graph cycle detection",
                    "Terminate deadlocked processes",
                    "Preempt resources from victims",
                    "Detection overhead vs deadlock cost",
                ],
                "narration": (
                    "The third strategy is to simply let deadlocks happen, then detect and recover from them. "
                    "Detection uses a simplified Resource Allocation Graph called the wait-for graph, where "
                    "edges connect processes directly. If the wait-for graph contains a cycle, the system is "
                    "deadlocked. Recovery has two options: terminate one or more deadlocked processes to break "
                    "the cycle, or preempt resources from a chosen victim process. The key trade-off is how "
                    "often to run detection — too frequent means wasted overhead, too infrequent means "
                    "processes stay blocked for longer."
                ),
                "visual_strategy": "Wait-for graph with cycle highlighted in red, recovery action breaks an edge",
            },
            {
                "title": "Real-World: Database Deadlocks",
                "objective": "Show how databases handle deadlocks with lock ordering and timeouts",
                "scene_type": "generated_still_with_motion",
                "duration_sec": 30,
                "key_points": [
                    "Two-phase locking (2PL)",
                    "Wait-for graph detection",
                    "Victim transaction rollback",
                    "Lock timeout as fallback",
                ],
                "narration": (
                    "Deadlocks aren't just theoretical — they happen in production databases every day. "
                    "Databases use two-phase locking to ensure serializable transactions, but this can create "
                    "circular waits when two transactions lock rows in opposite orders. Modern databases like "
                    "PostgreSQL and MySQL detect deadlocks by maintaining a wait-for graph and checking for "
                    "cycles. When a cycle is found, the database chooses a victim transaction — typically the "
                    "one with the least work done — and rolls it back. As an additional safety net, lock "
                    "timeouts ensure that even missed deadlocks eventually resolve."
                ),
                "visual_strategy": "Two transaction timelines with lock arrows crossing, victim marked for rollback",
            },
            {
                "title": "Summary & Strategy Comparison",
                "objective": "Compare all strategies and when to use each",
                "scene_type": "summary_scene",
                "duration_sec": 25,
                "key_points": [
                    "Prevention → restrictive, guaranteed",
                    "Avoidance → flexible, O(n²m) cost",
                    "Detection → permissive, needs recovery",
                    "Practice: combination of strategies",
                    "4 conditions → remove one to prevent",
                ],
                "narration": (
                    "Let's summarize. Deadlock requires all four Coffman conditions to hold simultaneously. "
                    "Prevention removes one condition structurally — simple but restrictive. Avoidance uses the "
                    "Banker's Algorithm to dynamically check safety — more flexible but with computational "
                    "overhead. Detection allows deadlocks and then recovers — the most permissive but requires "
                    "a recovery mechanism. In practice, real systems use a combination: resource ordering for "
                    "prevention, timeouts for detection, and careful application design to minimize deadlock "
                    "risk in the first place."
                ),
                "visual_strategy": "Comparison table: strategy rows, columns for overhead/flexibility/complexity",
            },
        ],
    },
    "rate limit": {
        "lesson_title": "Rate Limiter System Design",
        "style_preset": "clean_academic",
        "target_audience": "undergraduate CS student",
        "estimated_duration_sec": 300,
        "objectives": [
            "Explain why rate limiting protects APIs and backends",
            "Explain token bucket vs leaky bucket and when to use each",
            "Trace a request through gateway, limiter, and Redis-backed shared state",
            "Respond to throttling with HTTP 429 and Retry-After",
        ],
        "prerequisites": ["Basic HTTP and REST APIs", "Key-value stores (Redis basics)", "Distributed systems fundamentals"],
        "misconceptions": [
            "Rate limiting only prevents abuse — it also protects backend services from cascading failures",
            "Token bucket and leaky bucket are the same — token bucket allows bursts, leaky bucket enforces a steady rate",
            "Client-side rate limiting is sufficient — it can be bypassed; server-side is essential",
        ],
        "sections": [
            {
                "title": "Hook: When Traffic Spikes",
                "objective": "Establish stakes: overload, fairness, and abuse — why every public API needs a limiter",
                "scene_type": "veo_cinematic",
                "style_preset": "cinematic_minimal",
                "render_mode": "auto",
                "duration_sec": 28,
                "transition_note": "Next we anchor the architecture before diving into algorithms.",
                "continuity_anchor": CONTINUITY_MOTIF_RATE_LIMIT,
                "teaching_note": "Open with emotion + stakes; Veo carries motion here.",
                "key_points": ["Spike → queue → timeouts", "Fairness across tenants", "DDoS & abuse containment"],
                "narration": (
                    "Picture a viral post: traffic spikes tenfold in minutes. Without a rate limiter, "
                    "queues explode, threads block, and databases burn connection pools — one noisy neighbor can "
                    "take down the whole service. Rate limiting is how you cap work per client, preserve "
                    "headroom for everyone, and survive both flash crowds and malicious floods. "
                    "In this lesson we build intuition first, then algorithms, then where to put them in production."
                ),
                "visual_strategy": (
                    "Amber request particles stream toward a dark server stack; a teal gateway iris opens and "
                    "filters the stream into an orderly queue; subtle pulse waves show load flattening"
                ),
            },
            {
                "title": "Architecture: Where the Limiter Lives",
                "objective": "Show client → API gateway → services → Redis for shared counters",
                "scene_type": "system_design_graph",
                "style_preset": "clean_academic",
                "render_mode": "auto",
                "duration_sec": 42,
                "transition_note": "With that map in mind, we zoom into the token bucket.",
                "continuity_anchor": CONTINUITY_MOTIF_RATE_LIMIT,
                "teaching_note": "Single horizontal swimlane diagram; numbers on arrows.",
                "key_points": ["Gateway: single choke point", "Per-route vs global limits", "Redis: shared truth"],
                "narration": (
                    "Before we touch math, we need a map. Clients hit your API gateway — the front door. "
                    "That's the most common place to enforce rate limits: one policy before traffic fans out. "
                    "Behind the gateway, microservices may add their own finer limits. When multiple "
                    "instances need the same count, they share state in Redis: atomic increments, expiring keys, "
                    "sometimes Lua for complex windows. Client-side rate limits can help courtesy, but the "
                    "server must always enforce the real rule."
                ),
                "visual_strategy": (
                    "Left-to-right four panels: Client (mobile), API Gateway (teal badge RATE LIMIT), "
                    "Service pods, Redis cylinder with INCR/EXPIRE arrow; numbered arrows 1–4"
                ),
            },
            {
                "title": "Token Bucket: Bursts You Can Afford",
                "objective": "Explain refill rate, capacity, burst allowance, and rejection when empty",
                "scene_type": "deterministic_animation",
                "style_preset": "clean_academic",
                "render_mode": "auto",
                "duration_sec": 40,
                "transition_note": "Contrast with leaky bucket next — smooth vs bursty.",
                "continuity_anchor": CONTINUITY_MOTIF_RATE_LIMIT,
                "teaching_note": "Same teal/amber palette as hook for visual continuity.",
                "key_points": ["Refill r tokens/sec", "Capacity b", "Burst ≤ b", "Empty → reject"],
                "narration": (
                    "The token bucket is the workhorse of rate limiting. Tokens drip into a bucket at rate R, "
                    "up to a maximum capacity B. Each request consumes one token. If tokens are available, "
                    "you can burst — that's why APIs feel snappy under uneven traffic. If the bucket is empty, "
                    "you reject or queue. This model maps cleanly to many product SLAs: sustained average rate "
                    "with controlled bursts."
                ),
                "visual_strategy": (
                    "Cross-section bucket with teal tokens; curved arrow showing refill rate R; burst "
                    "cluster of amber dots leaving; empty state with red X"
                ),
            },
            {
                "title": "Leaky Bucket: Smooth Output",
                "objective": "Contrast constant drain vs token bucket; overflow when queue exceeds capacity",
                "scene_type": "deterministic_animation",
                "style_preset": "clean_academic",
                "render_mode": "auto",
                "duration_sec": 36,
                "transition_note": "Now we follow one request through the full path.",
                "continuity_anchor": CONTINUITY_MOTIF_RATE_LIMIT,
                "teaching_note": "Side-by-side mini compare with token bucket silhouette in corner.",
                "key_points": ["Drain at fixed rate", "Queue inside bucket", "Overflow dropped", "Smooth downstream"],
                "narration": (
                    "The leaky bucket shapes traffic differently. Requests enter a queue and drain to the "
                    "backend at a fixed rate — like a narrow pipe. That smooths spikes and protects fragile "
                    "downstreams. If the queue overflows, you drop. Choose token bucket when you want to allow "
                    "bursts; choose leaky when you need perfectly steady egress to databases or payment partners."
                ),
                "visual_strategy": (
                    "Vertical bucket with narrow leak at bottom; steady drip to downstream pipe; overflow spill "
                    "labeled drop"
                ),
            },
            {
                "title": "Request Flow: End-to-End",
                "objective": "Animate one HTTP request passing through limit check and Redis touch",
                "scene_type": "generated_still_with_motion",
                "style_preset": "modern_technical",
                "render_mode": "auto",
                "duration_sec": 38,
                "transition_note": "Finally, what the client sees when limited.",
                "continuity_anchor": CONTINUITY_MOTIF_RATE_LIMIT,
                "teaching_note": "High Veo score: motion shows packet flow.",
                "key_points": ["GET /api/…", "Limiter checks counter", "Redis INCR", "Allow or 429"],
                "narration": (
                    "Follow a single request. It hits the gateway; the limiter extracts a key — maybe tenant ID "
                    "plus route. It checks Redis: increment the counter, compare to threshold, set TTL on first "
                    "hit. Allow passes through to the service; deny returns a structured error. "
                    "That entire path is what your observability dashboards should trace."
                ),
                "visual_strategy": (
                    "Single glowing packet travels along curved path through gateway chip, Redis flash, "
                    "to service; alternate branch shows 429 fork"
                ),
            },
            {
                "title": "Throttling: 429, Retry-After, Backoff",
                "objective": "Teach HTTP 429, Retry-After header, and exponential backoff for clients",
                "scene_type": "generated_still_with_motion",
                "style_preset": "clean_academic",
                "render_mode": "auto",
                "duration_sec": 32,
                "transition_note": "We close with a design checklist.",
                "continuity_anchor": CONTINUITY_MOTIF_RATE_LIMIT,
                "teaching_note": "Still image + optional short Veo on retry timer.",
                "key_points": ["429 Too Many Requests", "Retry-After: seconds", "Backoff + jitter", "Hard vs soft limit"],
                "narration": (
                    "When you throttle, speak clearly. HTTP 429 tells the client they exceeded the limit. "
                    "Pair it with Retry-After so SDKs and browsers know when to try again. Good clients "
                    "implement exponential backoff with jitter — so a thundering herd doesn't retry in sync. "
                    "Hard limits drop immediately; soft limits might queue or delay — pick based on UX."
                ),
                "visual_strategy": (
                    "HTTP response card: status 429, headers Retry-After, timeline with exponential backoff steps"
                ),
            },
            {
                "title": "Recap & Design Checklist",
                "objective": "Summarize algorithms, placement, Redis, and client-facing behavior",
                "scene_type": "summary_scene",
                "style_preset": "clean_academic",
                "render_mode": "force_static",
                "duration_sec": 34,
                "transition_note": "",
                "continuity_anchor": CONTINUITY_MOTIF_RATE_LIMIT,
                "teaching_note": "Quiz follows in the app.",
                "key_points": [
                    "Pick bucket model for your traffic shape",
                    "Gateway + Redis for distributed truth",
                    "Sliding windows for precision (add-on)",
                    "429 + Retry-After for clients",
                ],
                "narration": (
                    "Here's your checklist. First, match the algorithm to your traffic: token bucket for bursts, "
                    "leaky bucket for smooth output, sliding or fixed windows when you need hard time precision. "
                    "Second, enforce at the gateway; add service limits where needed; share counters in Redis. "
                    "Third, always return actionable errors: 429 with Retry-After. "
                    "Do that, and your API stays fair, fast, and resilient."
                ),
                "visual_strategy": (
                    "3-column checklist: Algorithms | Placement | Client UX; small architecture thumbnail in footer"
                ),
            },
        ],
    },
}

# ---------------------------------------------------------------------------
# Scene-spec databases
# ---------------------------------------------------------------------------


def _build_scenes_for_plan(plan: dict, domain: str) -> list[dict]:
    """Build full SceneSpec dicts from a lesson-plan's sections."""
    sections = plan.get("sections", [])
    total = len(sections)
    scenes: list[dict] = []
    lesson_title = plan.get("lesson_title", domain)
    style_preset = plan.get("style_preset", "clean_academic")

    render_strategy_map = {
        "deterministic_animation": "remotion",
        "generated_still_with_motion": "image_to_video",
        "veo_cinematic": "veo",
        "code_trace": "remotion",
        "system_design_graph": "remotion",
        "summary_scene": "remotion",
    }
    mood_map = {
        "deterministic_animation": "focused",
        "code_trace": "focused",
        "system_design_graph": "neutral",
        "veo_cinematic": "dramatic",
        "generated_still_with_motion": "curious",
        "summary_scene": "uplifting",
    }

    prev_title = ""
    for idx, section in enumerate(sections):
        scene_type = section.get("scene_type", "deterministic_animation")
        render_strategy = render_strategy_map.get(scene_type, "default")
        render_mode = section.get("render_mode", "auto")

        base_narration = section.get("narration") or _narration_for_section(
            section, lesson_title, idx
        )
        bridge = ""
        if idx > 0 and prev_title:
            bridge = (
                f"Building on what we saw in {prev_title}, "
            )
        narration = f"{bridge}{base_narration}".strip()
        if section.get("transition_note"):
            narration = f"{narration} {section['transition_note']}".strip()

        visual_elements = [
            {"type": "title_text", "description": section["title"], "position": "top-center", "style": "bold-32"},
        ]
        for kp in section.get("key_points", []):
            visual_elements.append(
                {"type": "bullet_point", "description": kp, "position": "center-left", "style": "regular-24"}
            )

        duration = section.get("duration_sec", 30)
        beat_count = max(2, int(duration // 10))
        animation_beats = []
        for b in range(beat_count):
            t = round(b * (duration / beat_count), 1)
            if b == 0:
                animation_beats.append(
                    {"timestamp_sec": t, "action": "fade_in", "description": f"Introduce {section['title']}"}
                )
            elif b == beat_count - 1:
                animation_beats.append(
                    {"timestamp_sec": t, "action": "fade_out", "description": "Handoff to next scene"}
                )
            else:
                animation_beats.append(
                    {"timestamp_sec": t, "action": "reveal", "description": f"Reveal key point {b}"}
                )

        continuity_anchor = section.get("continuity_anchor") or (
            CONTINUITY_MOTIF_RATE_LIMIT
            if "rate" in lesson_title.lower() or "limit" in lesson_title.lower()
            else VISUAL_IDENTITY_TOKEN[:80]
        )

        veo_score = score_veo_eligibility(
            scene_type=scene_type,
            scene_index=idx,
            total_scenes=total,
            visual_strategy=section.get("visual_strategy", ""),
            title=section.get("title", ""),
            render_mode=render_mode,
        )
        veo_eligible = veo_score >= 0.42 and render_mode != "force_static"
        if render_mode == "force_veo":
            veo_eligible = True
        ve_dur = pick_veo_duration_sec(veo_score) if veo_eligible else None
        veo_prompt = (
            build_veo_prompt(
                lesson_title=lesson_title,
                scene_title=section.get("title", ""),
                visual_strategy=section.get("visual_strategy", ""),
                objective=section.get("objective", ""),
                continuity_anchor=continuity_anchor,
            )
            if veo_eligible
            else None
        )

        image_prompt = build_nano_banana_prompt(
            lesson_title=lesson_title,
            scene_title=section["title"],
            learning_objective=section.get("objective", ""),
            key_visual_idea=section.get("visual_strategy", section.get("objective", "")),
            style_preset=section.get("style_preset", style_preset),
            scene_type=scene_type,
            scene_index=idx,
            total_scenes=total,
            continuity_anchor=continuity_anchor,
            on_screen_bullets=section.get("key_points"),
        )

        asset_requests: list[dict] = [
            {"type": "image", "prompt": image_prompt, "provider": "image"},
        ]
        fallback_plan = section.get(
            "fallback_plan",
            "If motion fails: hold last Nano Banana frame with subtle Ken Burns zoom; keep narration.",
        )
        if veo_eligible and veo_prompt:
            asset_requests.append(
                {
                    "type": "video",
                    "prompt": veo_prompt,
                    "provider": "video",
                    "max_duration_sec": min(VEO_DURATION_MAX, max(3.0, ve_dur or 4.0)),
                }
            )

        transition_meta = {
            "transition_style": section.get("transition_style", "crossfade"),
            "transition_note": section.get("transition_note", ""),
            "continuity_anchor": continuity_anchor,
        }

        scenes.append({
            "scene_id": str(uuid.uuid4()),
            "lesson_title": lesson_title,
            "title": section["title"],
            "learning_objective": section.get("objective", ""),
            "teaching_note": section.get("teaching_note", ""),
            "source_refs": [],
            "scene_type": scene_type,
            "style_preset": section.get("style_preset", style_preset),
            "render_strategy": render_strategy,
            "render_mode": render_mode,
            "duration_sec": duration,
            "narration_text": narration,
            "on_screen_text": section.get("key_points", []),
            "visual_elements": visual_elements,
            "animation_beats": animation_beats,
            "asset_requests": asset_requests,
            "veo_eligible": veo_eligible,
            "veo_score": veo_score,
            "veo_prompt": veo_prompt,
            "image_prompt": image_prompt,
            "continuity_anchor": continuity_anchor,
            "transition_note": section.get("transition_note", ""),
            "fallback_plan": fallback_plan,
            "transition_metadata": transition_meta,
            "music_mood": mood_map.get(scene_type, "neutral"),
            "validation_notes": "",
        })
        prev_title = section.get("title", "")

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


def _planning_topic_match_key(concepts: dict, domain: str) -> str | None:
    """
    Resolve which curated _LESSON_PLANS key applies.

    Pipeline passes ``domain`` as the lesson enum (``cs``, ``system_design``), not the
    user's topic string, so we also scan concept graph labels and title.
    """
    hint_parts = [domain, concepts.get("title") or ""]
    cg = concepts.get("concept_graph")
    if isinstance(cg, dict):
        nodes = cg.get("nodes") or []
    else:
        nodes = concepts.get("nodes") or []
    for node in nodes[:16]:
        if isinstance(node, dict) and node.get("label"):
            hint_parts.append(str(node["label"]))
    return _match_topic(" ".join(hint_parts))


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


def _extract_topic_name(text: str) -> str:
    """Extract the actual topic name from source text or domain string."""
    for prefix in ["Topic: ", "Create a comprehensive educational lesson about: "]:
        if prefix.lower() in text.lower():
            idx = text.lower().index(prefix.lower()) + len(prefix)
            rest = text[idx:]
            for sep in [".", ",", "Domain:"]:
                if sep in rest:
                    return rest[:rest.index(sep)].strip()
            return rest.strip()
    return text.strip()


def _build_generic_concept_graph(topic: str) -> dict:
    """Build a rich concept graph for any topic using its name."""
    clean = topic.strip().title()
    topic_id = re.sub(r'[^a-z0-9]+', '_', topic.lower()).strip('_')

    nodes = [
        {"id": f"{topic_id}_core", "label": clean, "description": f"The fundamental concept of {clean} and its role in computer science.", "importance": 1.0, "prerequisites": []},
        {"id": f"{topic_id}_definition", "label": f"Definition of {clean}", "description": f"Formal definition and key terminology of {clean}.", "importance": 0.95, "prerequisites": [f"{topic_id}_core"]},
        {"id": f"{topic_id}_mechanism", "label": f"How {clean} Works", "description": f"The internal mechanism and step-by-step process behind {clean}.", "importance": 0.95, "prerequisites": [f"{topic_id}_definition"]},
        {"id": f"{topic_id}_types", "label": f"Types & Variants", "description": f"Different types, variants, and classifications of {clean}.", "importance": 0.9, "prerequisites": [f"{topic_id}_mechanism"]},
        {"id": f"{topic_id}_complexity", "label": "Complexity Analysis", "description": f"Time and space complexity analysis of {clean}.", "importance": 0.85, "prerequisites": [f"{topic_id}_mechanism"]},
        {"id": f"{topic_id}_tradeoffs", "label": "Trade-offs & Comparisons", "description": f"Comparing different approaches and understanding trade-offs in {clean}.", "importance": 0.85, "prerequisites": [f"{topic_id}_types", f"{topic_id}_complexity"]},
        {"id": f"{topic_id}_applications", "label": "Real-World Applications", "description": f"How {clean} is used in real software systems and practical scenarios.", "importance": 0.8, "prerequisites": [f"{topic_id}_tradeoffs"]},
        {"id": f"{topic_id}_pitfalls", "label": "Common Pitfalls", "description": f"Common mistakes and misconceptions when implementing or using {clean}.", "importance": 0.75, "prerequisites": [f"{topic_id}_mechanism"]},
    ]

    edges = [
        {"source": f"{topic_id}_core", "target": f"{topic_id}_definition", "relation_type": "defines"},
        {"source": f"{topic_id}_definition", "target": f"{topic_id}_mechanism", "relation_type": "explains"},
        {"source": f"{topic_id}_mechanism", "target": f"{topic_id}_types", "relation_type": "categorises"},
        {"source": f"{topic_id}_mechanism", "target": f"{topic_id}_complexity", "relation_type": "analysed_by"},
        {"source": f"{topic_id}_types", "target": f"{topic_id}_tradeoffs", "relation_type": "compared_in"},
        {"source": f"{topic_id}_complexity", "target": f"{topic_id}_tradeoffs", "relation_type": "informs"},
        {"source": f"{topic_id}_tradeoffs", "target": f"{topic_id}_applications", "relation_type": "applied_in"},
        {"source": f"{topic_id}_mechanism", "target": f"{topic_id}_pitfalls", "relation_type": "warns_about"},
    ]

    return {"nodes": nodes, "edges": edges, "title": clean}


def _build_generic_lesson_plan(topic: str, concepts: dict) -> dict:
    """Build a pedagogically structured lesson plan for any topic."""
    clean = topic.strip().title() if topic else "Computer Science Concepts"

    sections = [
        {
            "title": f"What is {clean}?",
            "objective": f"Define {clean} and motivate why it matters in computer science",
            "scene_type": "veo_cinematic",
            "duration_sec": 30,
            "key_points": [
                f"{clean} — core CS concept",
                "Why it matters in practice",
                "What we'll cover in this lesson",
            ],
            "narration": (
                f"Welcome to this lesson on {clean}. Before we dive into the mechanics, let's understand "
                f"why {clean} matters. It's a fundamental concept that shows up repeatedly in real systems, "
                f"from operating systems to distributed applications. By the end of this lesson, you'll "
                f"understand how {clean} works, when to use it, and how to avoid common pitfalls. "
                f"Let's start with the core idea."
            ),
            "visual_strategy": f"Cinematic introduction with {clean} visualised as a concept map",
            "teaching_note": "Hook the student with a motivating scenario before formal definitions.",
        },
        {
            "title": f"Core Mechanism of {clean}",
            "objective": f"Explain the internal workings and step-by-step process of {clean}",
            "scene_type": "deterministic_animation",
            "duration_sec": 40,
            "key_points": [
                f"How {clean} works internally",
                "Step-by-step process flow",
                "Key data structures involved",
                "Input → processing → output",
            ],
            "narration": (
                f"Now that we know why {clean} is important, let's look at how it actually works. "
                f"The core mechanism of {clean} involves a step-by-step process where data flows "
                f"from input through several stages to produce the desired output. Understanding this "
                f"flow is essential — once you see how each step connects to the next, the entire "
                f"concept becomes much clearer. Pay attention to the key data structures involved, "
                f"as they're what make {clean} efficient."
            ),
            "visual_strategy": f"Animated flowchart showing {clean} process step by step",
            "teaching_note": "Build from simple to complex. Show the 'happy path' first.",
        },
        {
            "title": f"Types and Variants",
            "objective": f"Explore different approaches and variants of {clean}",
            "scene_type": "system_design_graph",
            "duration_sec": 35,
            "key_points": [
                "Variant A: simplest approach",
                "Variant B: balanced trade-offs",
                "Variant C: most powerful",
                "Choosing the right one",
            ],
            "narration": (
                f"Like most concepts in computer science, {clean} isn't one-size-fits-all. There are "
                f"several variants, each with different trade-offs. The simplest approach is easy to "
                f"implement but may not handle all cases. More sophisticated variants offer greater power "
                f"at the cost of complexity. Understanding these trade-offs is crucial — the right choice "
                f"depends on your specific constraints: how much memory you have, how fast you need results, "
                f"and how complex your inputs are."
            ),
            "visual_strategy": f"Taxonomy diagram showing different types of {clean}",
            "teaching_note": "Frame as trade-offs, not 'best' vs 'worst'. Students remember comparisons.",
        },
        {
            "title": "Worked Example",
            "objective": f"Trace through a concrete example of {clean} in action",
            "scene_type": "code_trace",
            "duration_sec": 45,
            "key_points": [
                "Set up initial state",
                "Trace each step carefully",
                "Observe state changes",
                "Verify final result",
            ],
            "narration": (
                f"Theory only takes you so far — let's trace through a concrete example. We'll set up "
                f"a problem, apply {clean} step by step, and observe how the data transforms at each "
                f"stage. Watch carefully how each step connects to what we discussed earlier. By the end "
                f"of this trace, you should be able to predict the output for any similar input. This is "
                f"the kind of exercise that builds the intuition you need for exams and real implementations."
            ),
            "visual_strategy": f"Code trace with step-by-step execution of {clean}",
            "teaching_note": "Go slow here. Students need to trace alongside the visualization.",
        },
        {
            "title": "Complexity & Trade-offs",
            "objective": f"Analyse time/space complexity and key trade-offs of {clean}",
            "scene_type": "deterministic_animation",
            "duration_sec": 35,
            "key_points": [
                "Time: best / average / worst",
                "Space complexity",
                "Trade-off: speed vs memory",
                "When complexity matters",
            ],
            "narration": (
                f"Now let's analyze the performance characteristics. Understanding complexity isn't just "
                f"academic — it directly determines whether your solution will work in production. "
                f"We'll look at the best-case, average-case, and worst-case time complexity, as well as "
                f"space requirements. The key trade-off is almost always between speed and memory usage. "
                f"Knowing these numbers helps you make informed decisions when choosing between "
                f"different variants of {clean}."
            ),
            "visual_strategy": "Complexity comparison chart with Big-O curves",
            "teaching_note": "Connect complexity to real consequences (will it timeout? run out of memory?)",
        },
        {
            "title": "Real-World Applications",
            "objective": f"Show where {clean} is used in production systems",
            "scene_type": "generated_still_with_motion",
            "duration_sec": 30,
            "key_points": [
                "Used in databases & OS",
                "Web & distributed systems",
                "Industry implementations",
                "Choosing the right approach",
            ],
            "narration": (
                f"Where does {clean} actually show up in the real world? It's more common than you might "
                f"think. Database engines rely on it for query processing. Operating systems use it for "
                f"resource management. Web applications leverage it for performance optimization. And "
                f"in distributed systems, understanding {clean} is essential for building scalable "
                f"architectures. Knowing these applications helps you connect theory to practice."
            ),
            "visual_strategy": f"Architecture diagrams showing {clean} in real systems",
            "teaching_note": "Ground abstract concepts in familiar systems students already use.",
        },
        {
            "title": "Common Pitfalls",
            "objective": f"Identify mistakes and best practices for {clean}",
            "scene_type": "deterministic_animation",
            "duration_sec": 30,
            "key_points": [
                "Common implementation errors",
                "Edge cases to handle",
                "Best practices",
                "Testing strategies",
            ],
            "narration": (
                f"Before we wrap up, let's address the mistakes that trip up most students and "
                f"practitioners. The most common error is overlooking edge cases — situations where the "
                f"input is empty, has a single element, or contains duplicates. Another frequent mistake "
                f"is choosing the wrong variant for the problem at hand. Following best practices — "
                f"testing with boundary cases, starting with the simplest correct solution, and only "
                f"optimizing when needed — will save you hours of debugging."
            ),
            "visual_strategy": "Before/after comparison showing incorrect vs correct approaches",
            "teaching_note": "Address the exact mistakes students make on homework and exams.",
        },
        {
            "title": "Summary & Key Takeaways",
            "objective": f"Recap the essential concepts of {clean}",
            "scene_type": "summary_scene",
            "duration_sec": 25,
            "key_points": [
                f"{clean} → core mechanism",
                "Variants → choose by trade-off",
                "Complexity → know your bounds",
                "Practice → trace examples",
                "Pitfalls → test edge cases",
            ],
            "narration": (
                f"Let's recap what we've learned. {clean} is a fundamental concept with a clear "
                f"step-by-step mechanism. Different variants offer different trade-offs between simplicity, "
                f"speed, and power. Always analyze complexity to ensure your solution scales. Practice by "
                f"tracing through examples until the process feels automatic. And remember — test edge "
                f"cases, because that's where most bugs hide. With this foundation, you're ready to "
                f"apply {clean} confidently in both academic and production contexts."
            ),
            "visual_strategy": "Animated recap card with key takeaways",
            "teaching_note": "Reinforce the 3-4 things they should remember for exams.",
        },
    ]

    return {
        "lesson_title": clean,
        "target_audience": "undergraduate CS student",
        "estimated_duration_sec": sum(s["duration_sec"] for s in sections),
        "objectives": [
            f"Define and explain the core concepts of {clean}",
            f"Trace through a worked example of {clean}",
            f"Analyse the complexity and trade-offs of different {clean} approaches",
            f"Apply {clean} to solve practical problems",
        ],
        "prerequisites": ["Basic programming knowledge", "Data structures fundamentals"],
        "misconceptions": [
            f"There is only one way to implement {clean} — multiple variants exist with different trade-offs",
            f"{clean} is only theoretical — it has critical real-world applications",
            "Complexity analysis is not important — it directly affects system performance",
        ],
        "sections": sections,
    }


def _extract_paper_title(source_text: str) -> str:
    """Extract the paper title from formatted fragments."""
    for line in source_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Look for [title:paper_title] tag
        if "paper_title]" in line.lower():
            bracket_end = line.index("]")
            title = line[bracket_end + 1:].strip()
            if title and len(title) > 3:
                return title
        # Fallback: first [title] on page 1
        if line.lower().startswith("[title]") or line.lower().startswith("[title:"):
            bracket_end = line.index("]")
            title = line[bracket_end + 1:].strip()
            if title and len(title.split()) >= 3 and not _classify_paper_section_from_text(title):
                return title
    return ""


def _detect_paper_fragments(source_text: str) -> bool:
    """Check if the source text looks like it came from an academic paper."""
    lower = source_text.lower()
    section_markers = ["abstract", "introduction", "conclusion", "method", "results",
                       "related_work", "background", "paper_title"]
    hits = sum(1 for m in section_markers if f":{m}]" in lower or f"[{m}]" in lower)
    return hits >= 2


def _extract_paper_sections(source_text: str) -> dict[str, str]:
    """Group source text lines by academic section labels."""
    sections: dict[str, list[str]] = {}
    current_section = "body"
    for line in source_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("[") and "]" in line:
            bracket_end = line.index("]")
            tag = line[1:bracket_end].lower()
            text = line[bracket_end + 1:].strip()

            # Handle [kind:section] format from extraction service
            if ":" in tag:
                kind, section_label = tag.split(":", 1)
                if section_label and section_label != "none":
                    if section_label == "paper_title":
                        current_section = "body"
                    else:
                        current_section = section_label
                elif kind == "title":
                    sec = _classify_paper_section_from_text(text)
                    if sec:
                        current_section = sec
            elif tag == "title":
                sec = _classify_paper_section_from_text(text)
                if sec:
                    current_section = sec

            if text:
                sections.setdefault(current_section, []).append(text)
        else:
            sections.setdefault(current_section, []).append(line)
    return {k: " ".join(v)[:2000] for k, v in sections.items()}


def _classify_paper_section_from_text(text: str) -> str | None:
    """Classify a section heading text into an academic section label."""
    cleaned = re.sub(r"^\d+\.?\s*", "", text.strip()).lower()
    mapping = {
        "abstract": "abstract", "introduction": "introduction",
        "related work": "related_work", "background": "background",
        "method": "method", "approach": "method", "model": "method",
        "architecture": "method", "system": "method", "framework": "method",
        "experiment": "results", "evaluation": "results", "result": "results",
        "analysis": "results", "discussion": "discussion",
        "limitation": "discussion", "conclusion": "conclusion",
        "summary": "conclusion", "future": "conclusion",
        "reference": "references", "bibliography": "references",
    }
    for key, label in mapping.items():
        if cleaned.startswith(key):
            return label
    return None


def _build_paper_concept_graph(title: str, sections: dict[str, str]) -> dict:
    """Build a concept graph from paper section content."""
    nodes = [
        {"id": "paper_core", "label": title, "description": sections.get("abstract", title)[:200], "importance": 1.0, "prerequisites": []},
    ]
    edges = []

    section_labels = {
        "introduction": "Motivation & Context",
        "related_work": "Related Work",
        "background": "Background",
        "method": "Proposed Approach",
        "results": "Experiments & Results",
        "discussion": "Analysis & Discussion",
        "conclusion": "Contributions & Future Work",
    }

    for sec_key, label in section_labels.items():
        if sec_key in sections:
            node_id = sec_key.replace(" ", "_")
            first_sentence = sections[sec_key].split(".")[0][:150] + "."
            nodes.append({
                "id": node_id, "label": label,
                "description": first_sentence,
                "importance": 0.8, "prerequisites": ["paper_core"],
            })
            edges.append({"source": "paper_core", "target": node_id, "relation_type": "contains"})

    return {
        "title": title,
        "nodes": nodes,
        "edges": edges,
        "is_paper": True,
        "paper_sections": sections,
    }


def _build_paper_lesson_plan(title: str, sections: dict[str, str], concepts: dict) -> dict:
    """Build a lesson plan from an academic paper's extracted sections."""
    clean = title.strip()
    plan_sections = []

    # Scene 1: Paper overview
    abstract_text = sections.get("abstract", f"This paper presents research on {clean}.")[:300]
    plan_sections.append({
        "title": f"Paper Overview: {clean}",
        "objective": "Understand what this paper is about and why it matters",
        "scene_type": "veo_cinematic",
        "duration_sec": 30,
        "key_points": [
            f"Paper: {clean}",
            "Core contribution",
            "Why this research matters",
        ],
        "narration": (
            f"Welcome to this visual walkthrough of the paper: {clean}. "
            f"Here's the abstract in simplified terms: {abstract_text} "
            f"By the end of this walkthrough, you'll understand the key ideas, "
            f"the approach, and the results — without having to read the full paper."
        ),
        "visual_strategy": "Clean title card with paper name and key contribution",
        "teaching_note": "Hook the viewer — explain why they should care about this paper.",
    })

    # Scene 2: Introduction / Motivation
    if "introduction" in sections:
        intro_text = sections["introduction"][:400]
        plan_sections.append({
            "title": "Motivation & Problem Statement",
            "objective": "Understand the problem this paper addresses",
            "scene_type": "deterministic_animation",
            "duration_sec": 35,
            "key_points": [
                "The problem being solved",
                "Why existing approaches fall short",
                "Research gap identified",
            ],
            "narration": (
                f"Let's start with the motivation. {intro_text} "
                f"In essence, the authors identified a gap in existing approaches "
                f"and set out to address it with a new method."
            ),
            "visual_strategy": "Problem statement diagram with gap highlighted",
            "teaching_note": "Frame the problem clearly before diving into the solution.",
        })

    # Scene 3: Background / Related Work
    bg_text = sections.get("background", sections.get("related_work", ""))
    if bg_text:
        plan_sections.append({
            "title": "Background & Related Work",
            "objective": "Understand the context and prior work",
            "scene_type": "system_design_graph",
            "duration_sec": 30,
            "key_points": [
                "Key prior approaches",
                "What worked and what didn't",
                "Where this paper builds on",
            ],
            "narration": (
                f"To understand the contribution, we need context. {bg_text[:300]} "
                f"These prior approaches laid the groundwork, but each had limitations "
                f"that this paper aims to overcome."
            ),
            "visual_strategy": "Timeline or taxonomy of related approaches",
            "teaching_note": "Don't overwhelm — just enough context to appreciate the contribution.",
        })

    # Scene 4: Method / Approach (most important)
    method_text = sections.get("method", "")
    if method_text:
        plan_sections.append({
            "title": "Proposed Approach",
            "objective": "Understand the core method or architecture",
            "scene_type": "system_design_graph",
            "duration_sec": 45,
            "key_points": [
                "Core architecture / algorithm",
                "Key components",
                "How they connect",
                "What makes this approach novel",
            ],
            "narration": (
                f"Now the heart of the paper — the proposed approach. {method_text[:400]} "
                f"The key insight is what makes this method different from prior work. "
                f"Pay attention to how the components interact — that's where the novelty lies."
            ),
            "visual_strategy": "Architecture diagram showing the proposed system or algorithm",
            "teaching_note": "This is the scene viewers will revisit. Make it clear and structured.",
        })

    # Scene 5: Results
    results_text = sections.get("results", "")
    if results_text:
        plan_sections.append({
            "title": "Key Results",
            "objective": "Evaluate the paper's experimental findings",
            "scene_type": "code_trace",
            "duration_sec": 35,
            "key_points": [
                "Main experimental setup",
                "Key metrics and comparisons",
                "Best results achieved",
                "What the numbers mean",
            ],
            "narration": (
                f"Let's look at whether this approach actually works. {results_text[:350]} "
                f"The experiments compare against baseline methods across several metrics. "
                f"The numbers tell a clear story about the strengths and limitations of this approach."
            ),
            "visual_strategy": "Results comparison chart with highlighted improvements",
            "teaching_note": "Focus on what changed and by how much, not just 'it's better'.",
        })

    # Scene 6: Discussion / Limitations
    discussion_text = sections.get("discussion", "")
    if discussion_text:
        plan_sections.append({
            "title": "Discussion & Limitations",
            "objective": "Critically evaluate strengths and weaknesses",
            "scene_type": "generated_still_with_motion",
            "duration_sec": 25,
            "key_points": [
                "Main strengths",
                "Known limitations",
                "Open questions",
            ],
            "narration": (
                f"No paper is perfect — let's discuss the trade-offs. {discussion_text[:250]} "
                f"Understanding limitations is just as valuable as understanding contributions. "
                f"It tells us where future work is needed."
            ),
            "visual_strategy": "Strengths vs limitations comparison",
            "teaching_note": "Teach critical reading — what should a reader question?",
        })

    # Scene 7: Conclusion / Takeaways
    conclusion_text = sections.get("conclusion", f"This paper makes key contributions to {clean}.")
    plan_sections.append({
        "title": "Key Takeaways",
        "objective": "Summarize the paper's contributions",
        "scene_type": "summary_scene",
        "duration_sec": 25,
        "key_points": [
            "Main contribution",
            "Best result achieved",
            "Impact on the field",
            "Future directions",
        ],
        "narration": (
            f"Let's wrap up. {conclusion_text[:300]} "
            f"If you take away one thing from this paper, it's the core contribution: "
            f"a new approach to {clean} that advances the state of the art. "
            f"Future work will likely build on these ideas in exciting directions."
        ),
        "visual_strategy": "Summary card with key contributions and impact",
        "teaching_note": "End with what the reader should remember and cite.",
    })

    # Ensure at least 5 scenes for a reasonable walkthrough
    if len(plan_sections) < 4:
        plan_sections.insert(1, {
            "title": "Core Concepts",
            "objective": f"Understand the foundational ideas in {clean}",
            "scene_type": "deterministic_animation",
            "duration_sec": 35,
            "key_points": ["Key concept 1", "Key concept 2", "How they relate"],
            "narration": (
                f"Before we dive into the details, let's establish the core concepts. "
                f"This paper builds on several foundational ideas that you need to understand "
                f"to appreciate the contribution."
            ),
            "visual_strategy": f"Concept map for {clean}",
            "teaching_note": "Build vocabulary before diving into the method.",
        })

    return {
        "lesson_title": clean,
        "is_paper_walkthrough": True,
        "target_audience": "graduate CS student or researcher",
        "estimated_duration_sec": sum(s["duration_sec"] for s in plan_sections),
        "objectives": [
            f"Understand the core contribution of '{clean}'",
            "Evaluate the proposed approach critically",
            "Summarize key results and limitations",
        ],
        "prerequisites": ["Domain-specific background knowledge"],
        "misconceptions": [
            "A paper walkthrough replaces reading the paper — it's a complement, not a substitute",
            "All results should be taken at face value — always check methodology",
        ],
        "sections": plan_sections,
    }


class MockLLMProvider(LLMProvider):
    """Mock LLM that returns rich, pre-built educational content for demo purposes."""

    async def extract_concepts(self, source_text: str, domain: str) -> dict:
        if _detect_paper_fragments(source_text):
            sections = _extract_paper_sections(source_text)
            paper_title = _extract_paper_title(source_text) or domain
            logger.info("MockLLM: extract_concepts detected paper '%s' with %d sections",
                        paper_title, len(sections))
            return _build_paper_concept_graph(paper_title, sections)

        topic = _match_topic(source_text) or _match_topic(domain)
        if topic and topic in _CONCEPT_GRAPHS:
            logger.info("MockLLM: extract_concepts matched topic '%s'", topic)
            return _CONCEPT_GRAPHS[topic]

        topic_name = _extract_topic_name(source_text)
        if not topic_name or topic_name.lower() == domain.lower():
            topic_name = domain
        logger.info("MockLLM: extract_concepts building graph for '%s'", topic_name)
        return _build_generic_concept_graph(topic_name)

    async def create_lesson_plan(self, concepts: dict, domain: str, style: str) -> dict:
        if concepts.get("is_paper"):
            paper_title = concepts.get("title", domain)
            logger.info("MockLLM: create_lesson_plan building paper walkthrough for '%s'", paper_title)
            sections = concepts.get("paper_sections", {})
            if not sections:
                for node in concepts.get("nodes", []):
                    nid = node.get("id", "")
                    if nid != "paper_core":
                        sections[nid] = node.get("description", "")
            return _build_paper_lesson_plan(paper_title, sections, concepts)

        topic = _planning_topic_match_key(concepts, domain)
        if topic and topic in _LESSON_PLANS:
            logger.info("MockLLM: create_lesson_plan matched topic '%s'", topic)
            return _LESSON_PLANS[topic]

        topic_name = concepts.get("title") or _extract_topic_name(domain) or domain
        logger.info("MockLLM: create_lesson_plan building plan for '%s'", topic_name)
        return _build_generic_lesson_plan(topic_name, concepts)

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

        topic_name = _extract_topic_name(domain) or domain
        logger.info("MockLLM: generate_quiz building questions for '%s'", topic_name)

        scene_titles = [s.get("title", "") for s in scenes[:4]] if scenes else []
        key_points_all = []
        for s in scenes[:4]:
            key_points_all.extend(s.get("on_screen_text", [])[:2])

        questions = [
            {
                "question": f"What is the primary purpose of {topic_name}?",
                "options": [
                    f"To implement {topic_name} in hardware circuits",
                    f"To understand and apply the core principles of {topic_name} for efficient computing",
                    f"To replace all existing programming languages",
                    f"To memorise formulas without understanding",
                ],
                "correct_answer": 1,
                "explanation": f"The primary purpose of studying {topic_name} is to understand and apply its core principles for building efficient software systems.",
            },
        ]

        if len(key_points_all) >= 2:
            questions.append({
                "question": f"Which of the following is a key aspect of {topic_name}?",
                "options": [
                    "User interface design patterns",
                    key_points_all[0] if key_points_all else f"Understanding {topic_name} fundamentals",
                    "Network protocol specifications",
                    "Database schema normalisation",
                ],
                "correct_answer": 1,
                "explanation": f"This is a fundamental concept covered in the {topic_name} lesson.",
            })

        questions.append({
            "question": f"When analysing {topic_name}, which type of complexity is most commonly discussed?",
            "options": [
                "Code complexity (lines of code)",
                "Time and space complexity using Big-O notation",
                "Team organisational complexity",
                "User experience complexity",
            ],
            "correct_answer": 1,
            "explanation": "Time and space complexity analysis using Big-O notation is the standard way to analyse algorithmic performance.",
        })

        if scene_titles and len(scene_titles) > 2:
            questions.append({
                "question": f"In the context of {topic_name}, which step typically comes first?",
                "options": [
                    "Optimisation and tuning",
                    "Benchmarking against alternatives",
                    "Understanding the problem and defining the approach",
                    "Deploying to production",
                ],
                "correct_answer": 2,
                "explanation": "Understanding the problem is always the first step before implementing or optimising any solution.",
            })

        questions.append({
            "question": f"Why is it important to know multiple approaches to {topic_name}?",
            "options": [
                "To make code more complex",
                "Different approaches have different trade-offs; choosing the right one depends on the use case",
                "Only one approach is ever correct",
                "Multiple approaches are only needed for exams",
            ],
            "correct_answer": 1,
            "explanation": f"Different approaches to {topic_name} offer different trade-offs in time complexity, space complexity, and implementation complexity. Choosing the right one depends on the specific constraints of your problem.",
        })

        return questions

    async def evaluate_lesson(self, lesson_data: dict) -> dict:
        logger.info("MockLLM: evaluate_lesson (context-aware)")
        scenes = lesson_data.get("scenes", [])
        title = lesson_data.get("title", "")
        scene_count = len(scenes)

        has_narration = sum(1 for s in scenes if (s.get("narration_text") or "").strip())
        has_visuals = sum(1 for s in scenes if s.get("visual_elements") or s.get("on_screen_text"))
        types = set(s.get("scene_type", "") for s in scenes)
        type_variety = len(types)

        content_score = min(0.95, 0.75 + 0.03 * has_narration)
        pedagogy_score = min(0.95, 0.70 + 0.04 * min(scene_count, 6))
        visual_score = min(0.92, 0.65 + 0.04 * type_variety + 0.02 * has_visuals)
        narration_score = min(0.93, 0.70 + 0.03 * has_narration)
        engagement_score = min(0.90, 0.65 + 0.05 * min(type_variety, 5))

        overall = round(
            0.25 * content_score + 0.25 * pedagogy_score +
            0.20 * visual_score + 0.15 * narration_score +
            0.15 * engagement_score, 3
        )

        suggestions = []
        if scene_count < 5:
            suggestions.append(f"Only {scene_count} scenes — consider adding more depth")
        if type_variety < 3:
            suggestions.append("Low variety in scene types — mix animation, code trace, and diagrams")
        if has_narration < scene_count:
            suggestions.append(f"{scene_count - has_narration} scenes lack narration — fill these for completeness")
        if "summary_scene" not in types:
            suggestions.append("Add a recap/summary scene to reinforce key takeaways")
        suggestions.append(f"'{title}' lesson: consider linking to further reading or next topics")

        return {
            "overall_score": overall,
            "content_accuracy": {
                "score": round(content_score, 2),
                "feedback": f"Content covers {scene_count} sections with {has_narration} narrated. "
                            "Key terminology is used correctly across scenes.",
            },
            "pedagogical_quality": {
                "score": round(pedagogy_score, 2),
                "feedback": "Good scaffolding from concepts to applications. "
                            "The lesson builds progressively." if scene_count >= 4
                            else "Lesson is brief — consider adding worked examples.",
            },
            "visual_quality": {
                "score": round(visual_score, 2),
                "feedback": f"{type_variety} distinct scene types provide visual variety. "
                            "Diagrams and animations support understanding.",
            },
            "narration_quality": {
                "score": round(narration_score, 2),
                "feedback": "Narration maintains appropriate pace and clarity. "
                            "Transitions between scenes flow naturally.",
            },
            "engagement": {
                "score": round(engagement_score, 2),
                "feedback": f"Scene variety ({type_variety} types) keeps attention. "
                            "The lesson structure supports sustained engagement.",
            },
            "flags": [],
            "suggestions": suggestions[:5],
        }
