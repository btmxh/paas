import sys
from .parser import parse_input

def main():
    try:
        instance = parse_input(sys.stdin)
        print(f"Loaded problem instance with {instance.num_tasks} tasks and {instance.num_teams} teams.")
        print(f"Total dependencies: {sum(len(t.successors) for t in instance.tasks.values())}")
        print(f"Total assignments possible: {sum(len(t.compatible_teams) for t in instance.tasks.values())}")
    except Exception as e:
        print(f"Error parsing input: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
