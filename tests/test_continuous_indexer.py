import unittest
from typing import Dict

from paas.middleware.continuous_indexer import ContinuousIndexer
from paas.middleware.base import Runnable
from paas.models import ProblemInstance, Schedule, Task, Assignment, Team


class MockSolver(Runnable):
    def run(
        self, problem: ProblemInstance, time_limit: float = float("inf")
    ) -> Schedule:
        # Verify that the problem has continuous indices
        expected_ids = set(range(problem.num_tasks))
        actual_ids = set(problem.tasks.keys())
        if expected_ids != actual_ids:
            raise ValueError(
                f"Indices are not continuous. Expected {expected_ids}, got {actual_ids}"
            )

        # Verify dependencies are remapped
        # In the test case:
        # 1 -> 0
        # 5 -> 1
        # 10 -> 2
        # Original: 1->5 (0->1), 5->10 (1->2)

        task0 = problem.tasks[0]  # old 1
        task1 = problem.tasks[1]  # old 5
        # task2 = problem.tasks[2] # old 10

        if 1 not in task0.successors:
            raise ValueError("Dependency 0->1 missing")
        if 0 not in task1.predecessors:
            raise ValueError("Dependency 0->1 (pred) missing")
        if 2 not in task1.successors:
            raise ValueError("Dependency 1->2 missing")

        # Return a schedule using new IDs
        assignments = [
            Assignment(task_id=0, team_id=0, start_time=0),
            Assignment(task_id=1, team_id=0, start_time=10),
            Assignment(task_id=2, team_id=0, start_time=20),
        ]
        return Schedule(assignments=assignments)


class TestContinuousIndexer(unittest.TestCase):
    def test_relabeling(self):
        # Create a problem with non-continuous indices
        # IDs: 1, 5, 10
        # Deps: 1 -> 5 -> 10

        tasks: Dict[int, Task] = {
            1: Task(id=1, duration=10, successors=[5], compatible_teams={100: 1}),
            5: Task(
                id=5,
                duration=10,
                predecessors=[1],
                successors=[10],
                compatible_teams={100: 1},
            ),
            10: Task(id=10, duration=10, predecessors=[5], compatible_teams={100: 1}),
        }

        teams: Dict[int, Team] = {100: Team(id=100, available_from=0)}

        problem = ProblemInstance(num_tasks=3, num_teams=1, tasks=tasks, teams=teams)

        middleware = ContinuousIndexer()
        solver = MockSolver()

        # Run
        schedule = middleware.run(problem, solver)

        # Check result
        # Should be mapped back to 1, 5, 10
        self.assertEqual(len(schedule.assignments), 3)

        # Sort by start time to check order
        assignments = sorted(schedule.assignments, key=lambda x: x.start_time)

        self.assertEqual(assignments[0].task_id, 1)
        self.assertEqual(assignments[1].task_id, 5)
        self.assertEqual(assignments[2].task_id, 10)


if __name__ == "__main__":
    unittest.main()
