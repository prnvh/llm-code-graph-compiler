import argparse
import json

from core.validator import validate_plan
from core.compiler import compile_output, write_output
from core.planner import plan_from_nodes, load_plan, get_plan


def main():
    print("CLI STARTED")
    parser = argparse.ArgumentParser()

    parser.add_argument("--nodes", nargs="*")
    parser.add_argument("--plan")
    parser.add_argument("--task", type=str)
    parser.add_argument("--output", default="output/app.py")

    args = parser.parse_args()

    # ------------------------------
    # Plan resolution priority
    # ------------------------------

    plan = None

    if args.plan:
        plan = load_plan(args.plan)

    elif args.task:
        plan = get_plan(args.task)

    elif args.nodes:
        plan = plan_from_nodes(args.nodes)

    else:
        print("Provide --nodes, --plan, or --task")
        return

    # ------------------------------
    # Validation pipeline
    # ------------------------------

    ok, errors = validate_plan(plan)

    if not ok:
        print("Validation Failed\n")

        for e in errors:
            print(e)

        return

    # ------------------------------
    # Compilation pipeline
    # ------------------------------

    code = compile_output(plan)
    write_output(code, args.output)

    print("\nCompilation successful.")


if __name__ == "__main__":
    main()