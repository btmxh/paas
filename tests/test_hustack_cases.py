import unittest
import os
from paas.parser import parse_input
from paas.middleware.cycle_remover import CycleRemover
from paas.middleware.impossible_task_remover import ImpossibleTaskRemover
from paas.middleware.dependency_pruner import DependencyPruner


class TestHustackCases(unittest.TestCase):
    def setUp(self):
        # Assuming run from project root
        self.data_dir = os.path.join(os.getcwd(), "data", "hustack")

    def test_hustack_cases(self):
        # Iterate through tc01 to tc10
        for i in range(1, 11):
            case_name = f"tc{i:02d}"
            input_path = os.path.join(self.data_dir, case_name, "input.txt")
            jury_path = os.path.join(self.data_dir, case_name, "jury.txt")

            if not os.path.exists(input_path) or not os.path.exists(jury_path):
                print(f"Skipping {case_name}: files not found")
                continue

            with self.subTest(case=case_name):
                print(f"Processing {case_name}")
                # 1. Parse Input
                with open(input_path, "r") as f:
                    problem = parse_input(f)

                # 2. Parse Jury for Objective 1
                with open(jury_path, "r") as f:
                    line = f.readline()
                    try:
                        jury_r = int(line.strip())
                    except ValueError:
                        self.fail(f"Invalid jury file format for {case_name}")

                # 3. Run Middleware Pipeline
                # With the fix in ImpossibleTaskRemover, we can now simply run the pipeline.

                p = problem

                # 1. Remove tasks with no teams (and clean their refs -> Soft Dependency)
                p = ImpossibleTaskRemover().map_problem(p)

                # 2. Remove cycles (and leave dangling refs for Pruner)
                p = CycleRemover().map_problem(p)

                # 3. Prune tasks that depended on removed tasks (Hard Dependency for Cycles)
                p = DependencyPruner().map_problem(p)

                # Check
                self.assertEqual(
                    len(p.tasks),
                    jury_r,
                    f"Failed for {case_name}: Expected {jury_r} tasks, got {len(p.tasks)}",
                )


if __name__ == "__main__":
    unittest.main()
