from collections import defaultdict, deque
from nodes.registry import NODE_REGISTRY
from nodes.types import NodeType


def validate_plan(plan: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []

    nodes = plan.get("nodes", [])
    edges = plan.get("edges", [])
    parameters = plan.get("parameters", {})

    # ---- CHECK 1: Node existence ----
    for node_name in nodes:
        if node_name not in NODE_REGISTRY:
            errors.append(f"NODE_NOT_FOUND: '{node_name}' not in registry.")

    if errors:
        return False, errors

    # ---- CHECK 2: Edge references valid nodes ----
    for source, target in edges:
        if source not in nodes or target not in nodes:
            errors.append(
                f"EDGE_INVALID: [{source} -> {target}] references undefined node."
            )

    # ---- CHECK 3: Type compatibility ----
    for source, target in edges:
        if source not in NODE_REGISTRY or target not in NODE_REGISTRY:
            continue

        source_output = NODE_REGISTRY[source].output_type
        target_input = NODE_REGISTRY[target].input_type

        if target_input != NodeType.ANY and source_output != target_input:
            errors.append(
                f"TYPE_MISMATCH: [{source} -> {target}] "
                f"{source_output} != {target_input}"
            )

    # ---- CHECK 4: Cycle detection (topological sort) ----
    adj = defaultdict(list)
    in_degree = {node: 0 for node in nodes}

    for source, target in edges:
        adj[source].append(target)
        in_degree[target] += 1

    queue = deque([n for n in nodes if in_degree[n] == 0])
    visited = 0

    while queue:
        node = queue.popleft()
        visited += 1
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited != len(nodes):
        errors.append("CYCLE_DETECTED: graph contains a cycle.")

    # ---- CHECK 5: Orphan nodes ----
    connected = set()
    for source, target in edges:
        connected.add(source)
        connected.add(target)

    for node in nodes:
        if len(nodes) > 1 and node not in connected:
            errors.append(f"ORPHAN_NODE: '{node}' is disconnected.")

    # ---- CHECK 6: Required parameters present ----
    for node_name in nodes:
        node = NODE_REGISTRY[node_name]
        provided = parameters.get(node_name, {})

        for param in node.required_params:
            if param not in provided:
                errors.append(
                    f"MISSING_PARAM: '{node_name}' requires '{param}'."
                )

    return len(errors) == 0, errors