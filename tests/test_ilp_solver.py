import unittest
from typing import Dict

from paas.solvers.ilp_solver import ILPSolver
from paas.models import ProblemInstance, Task, Team


class TestILPSolver(unittest.TestCase):
    def test_simple_case(self):
        # 3 Tasks: 1->2->3
        # Teams: T1 (start 0)
        # Durations: 10 each

        tasks: Dict[int, Task] = {
            1: Task(id=1, duration=10, successors=[2], compatible_teams={100: 10}),
            2: Task(
                id=2,
                duration=10,
                predecessors=[1],
                successors=[3],
                compatible_teams={100: 10},
            ),
            3: Task(id=3, duration=10, predecessors=[2], compatible_teams={100: 10}),
        }

        teams: Dict[int, Team] = {100: Team(id=100, available_from=0)}

        problem = ProblemInstance(num_tasks=3, num_teams=1, tasks=tasks, teams=teams)

        solver = ILPSolver()
        schedule = solver.run(problem)

        self.assertEqual(len(schedule.assignments), 3)

        # Verify order
        # Sort by start time
        assigns = sorted(schedule.assignments, key=lambda x: x.start_time)

        # Should be task 1, then 2, then 3
        self.assertEqual(assigns[0].task_id, 1)
        self.assertEqual(assigns[0].start_time, 0)

        self.assertEqual(assigns[1].task_id, 2)
        self.assertEqual(assigns[1].start_time, 10)

        self.assertEqual(assigns[2].task_id, 3)
        self.assertEqual(assigns[2].start_time, 20)

    def test_optimization_goals(self):
        # 2 tasks, independent.
        # Task 1: dur=10. Costs: T1=10, T2=5.
        # Task 2: dur=10. Costs: T1=5, T2=10.
        # T1 start=0, T2 start=0.

        # To minimize cost, T1 takes Task 2, T2 takes Task 1. Total cost = 5+5=10.
        # Makespan = 10.

        tasks: Dict[int, Task] = {
            1: Task(id=1, duration=10, compatible_teams={1: 10, 2: 5}),
            2: Task(id=2, duration=10, compatible_teams={1: 5, 2: 10}),
        }
        teams: Dict[int, Team] = {
            1: Team(id=1, available_from=0),
            2: Team(id=2, available_from=0),
        }

        problem = ProblemInstance(num_tasks=2, num_teams=2, tasks=tasks, teams=teams)

        solver = ILPSolver()
        schedule = solver.run(problem)

        self.assertEqual(len(schedule.assignments), 2)

        t1_assign = next(a for a in schedule.assignments if a.task_id == 1)
        t2_assign = next(a for a in schedule.assignments if a.task_id == 2)

        self.assertEqual(t1_assign.team_id, 2)  # Cheaper
        self.assertEqual(t2_assign.team_id, 1)  # Cheaper

        self.assertEqual(t1_assign.start_time, 0)
        self.assertEqual(t2_assign.start_time, 0)


if __name__ == "__main__":
    unittest.main()
