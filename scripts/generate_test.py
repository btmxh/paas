import argparse
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from paas.generator import generate_instance, serialize_instance


def main():
    parser = argparse.ArgumentParser(
        description="Generate a random PaaS problem instance."
    )
    parser.add_argument("--tasks", type=int, default=10, help="Number of tasks")
    parser.add_argument("--teams", type=int, default=3, help="Number of teams")
    parser.add_argument(
        "--dep-ratio", type=float, default=0.2, help="Dependency ratio (0 to 1)"
    )
    parser.add_argument(
        "--comp-ratio", type=float, default=0.5, help="Compatibility ratio (0 to 1)"
    )
    parser.add_argument(
        "--max-duration", type=int, default=100, help="Maximum task duration"
    )
    parser.add_argument(
        "--max-start", type=int, default=50, help="Maximum team start time"
    )
    parser.add_argument("--max-cost", type=int, default=100, help="Maximum cost")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument(
        "--output", type=str, default=None, help="Output file path (default: stdout)"
    )

    args = parser.parse_args()

    instance = generate_instance(
        n_tasks=args.tasks,
        n_teams=args.teams,
        dependency_ratio=args.dep_ratio,
        compatibility_ratio=args.comp_ratio,
        max_duration=args.max_duration,
        max_start_time=args.max_start,
        max_cost=args.max_cost,
        seed=args.seed,
    )

    serialized = serialize_instance(instance)

    if args.output:
        with open(args.output, "w") as f:
            f.write(serialized)
            f.write("\n")
        print(
            f"Generated instance with {args.tasks} tasks and {args.teams} teams to {args.output}"
        )
    else:
        print(serialized)


if __name__ == "__main__":
    main()
