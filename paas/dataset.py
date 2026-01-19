from paas.parser import parse_input, parse_solution
from dataclasses import dataclass
from typing import Optional, List
from paas.models import ProblemInstance, Schedule
import os


@dataclass
class Instance:
    id: str
    problem: ProblemInstance
    sample_solution_result: Optional[Schedule] = None
    optimal_solution_result: Optional[Schedule] = None


@dataclass
class Dataset:
    instances: List[Instance]

    @staticmethod
    def hustack() -> "Dataset":
        instances = []
        for tc in range(1, 11):
            # Resolve paths relative to project root, assuming running from root
            input_path = f"data/hustack/tc{tc:02}/input.txt"
            jury_path = f"data/hustack/tc{tc:02}/jury.txt"
            optimal_path = f"data/hustack/tc{tc:02}/sol_cp.txt"

            if not os.path.exists(input_path):
                # Fallback or error? For now assume paths are correct relative to cwd
                continue

            with open(input_path, "r") as f:
                problem = parse_input(f)

            sample_solution = None
            if os.path.exists(jury_path):
                with open(jury_path, "r") as f:
                    sample_solution = parse_solution(f)
            if os.path.exists(optimal_path):
                with open(optimal_path, "r") as f:
                    optimal_solution = parse_solution(f)

            instances.append(
                Instance(
                    f"hustack/tc{tc:02}", problem, sample_solution, optimal_solution
                )
            )
        return Dataset(instances)
