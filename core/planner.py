import json
from openai import OpenAI
from nodes.registry import NODE_REGISTRY

client = OpenAI()


def build_node_summary() -> str:
    lines = []

    for name, node in NODE_REGISTRY.items():
        lines.append(
            f"- {name}: {node.description} | input: {node.input_type} | output: {node.output_type} | required params: {node.required_params}"
        )

    return "\n".join(lines)


def plan_from_nodes(nodes: list[str]) -> dict:
    edges = []
    parameters = {}

    if len(nodes) == 0:
        return {"nodes": [], "edges": [], "parameters": {}, "glue_code": ""}

    for i in range(len(nodes) - 1):
        edges.append((nodes[i], nodes[i + 1]))
        parameters.setdefault(nodes[i], {})

    parameters.setdefault(nodes[-1], {})

    return {
        "nodes": nodes,
        "edges": edges,
        "parameters": parameters,
        "glue_code": ""
    }


def load_plan(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


SYSTEM_PROMPT = """
You are a code graph planner.

You select nodes from a fixed library and connect them to solve the user's task.

Output STRICTLY raw JSON.

Response format must be:

{
  "nodes": [],
  "edges": [],
  "parameters": {},
  "flags": [],
  "glue_code": ""
}

Rules:

- Only use nodes from the provided library.
- Never invent nodes.
- Every edge must be type-compatible.
- If a required node is missing, add flag MISSING_NODE.
- If credentials are needed, add flag REQUIRED_CREDENTIAL.
- Glue code must follow topological execution order.
- Return raw JSON only.
"""


def get_plan(task_description: str) -> dict:
    node_summary = build_node_summary()

    user_message = f"""
Available Nodes:
{node_summary}

Task:
{task_description}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0
    )

    raw = response.choices[0].message.content.strip()
    return json.loads(raw)