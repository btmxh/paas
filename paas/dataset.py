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

    @staticmethod
    def generated() -> "Dataset":
        instances = []
        base_directory = "data/generated_dataset"

        if not os.path.exists(base_directory):
            return Dataset([])

        # Iterate through each item in the base directory
        # sorted() ensures small_1, small_2, etc., are processed in order
        for subdir in sorted(os.listdir(base_directory)):
            subdir_path = os.path.join(base_directory, subdir)

            # Check if it's a directory and contains the target file
            if os.path.isdir(subdir_path):
                input_path = os.path.join(subdir_path, "input.txt")

                if os.path.exists(input_path):
                    # Use the subdirectory name (e.g., 'small_1') as the ID
                    instance_id = subdir

                    with open(input_path, "r") as f:
                        problem = parse_input(f)

                    sol_cp_path = os.path.join(subdir_path, "sol_cp.txt")
                    with open(sol_cp_path, "r") as f:
                        optimal_solution = parse_solution(f)
                    instances.append(
                        Instance(
                            instance_id,
                            problem,
                            optimal_solution_result=optimal_solution,
                        )
                    )

        return Dataset(instances)
