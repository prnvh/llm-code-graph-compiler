from nodes.registry import NODE_REGISTRY
from nodes.types import NodeType


def reliability_score(plan: dict) -> float:
    nodes = plan.get("nodes", [])
    edges = plan.get("edges", [])

    if not nodes:
        return 0.0

    structural_score = 0.0
    type_score = 0.0

    connected = set()

    # Structural connectivity reward
    for s, t in edges:
        connected.add(s)
        connected.add(t)

    orphan_penalty = sum(1 for n in nodes if n not in connected)
    structural_score += max(0.0, 1.0 - orphan_penalty / len(nodes))
    structural_score += len(edges) / max(1, len(nodes))

    # Type compatibility scoring
    for s, t in edges:
        if s not in NODE_REGISTRY or t not in NODE_REGISTRY:
            continue

        src_out = NODE_REGISTRY[s].output_type
        tgt_in = NODE_REGISTRY[t].input_type

        if tgt_in == NodeType.ANY:
            type_score += 1.0
        elif src_out == tgt_in:
            type_score += 1.0
        else:
            type_score += 0.3

    if edges:
        type_score /= len(edges)

    return 0.4 * structural_score + 0.6 * type_score