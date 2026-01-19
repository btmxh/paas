#!/usr/bin/env python3
import sys
import os
import argparse

# Ensure the project root is in sys.path so we can import 'paas'
# Assuming this script is run from the project root or from scripts/
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from paas.parser import parse_input, parse_solution
    from paas.grader import grade_schedule
except ImportError as e:
    print(f"Error importing paas modules: {e}")
    print(
        "Make sure you are running this script from the project root or have set PYTHONPATH correctly."
    )
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Grade a solution against a problem instance."
    )
    parser.add_argument("input_file", help="Path to the problem input file")
    parser.add_argument("solution_file", help="Path to the solution output file")

    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' not found.")
        sys.exit(1)

    if not os.path.exists(args.solution_file):
        print(f"Error: Solution file '{args.solution_file}' not found.")
        sys.exit(1)

    try:
        with open(args.input_file, "r") as f:
            problem = parse_input(f)

        with open(args.solution_file, "r") as f:
            solution = parse_solution(f)

        score = grade_schedule(problem, solution)

        print(f"Tasks: {score.num_tasks}")
        print(f"Makespan: {score.makespan}")
        print(f"Cost: {score.total_cost}")

    except Exception as e:
        print(f"Error during grading: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
