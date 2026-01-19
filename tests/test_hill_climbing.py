import unittest
from paas.models import ProblemInstance, Task, Team, Assignment, Schedule
from paas.middleware.hill_climbing import HillClimbingMiddleware


class TestHillClimbingMiddleware(unittest.TestCase):
    def test_improvement(self):
        # Create a simple problem where a bad schedule can be improved
        # Task 0: 10s, Team A (fast) or B (slow)
        # Task 1: 10s, Team A or B
        # No dependencies

        # Scenario:
        # Team A available 0
        # Team B available 0
        # Optimal: Task 0 -> A, Task 1 -> B (Makespan 10)
        # Suboptimal: Task 0 -> A, Task 1 -> A (Makespan 20)

        tasks = {
            0: Task(0, 10, [], [], {0: 10, 1: 10}),
            1: Task(1, 10, [], [], {0: 10, 1: 10}),
        }
        teams = {
            0: Team(0, 0),
            1: Team(1, 0),
        }
        problem = ProblemInstance(2, 2, tasks, teams)

        # Create suboptimal schedule (Both on Team 0)
        assignments = [
            Assignment(0, 0, 0),  # T0 on Team 0, 0-10
            Assignment(1, 0, 10),  # T1 on Team 0, 10-20
        ]
        schedule = Schedule(assignments)

        middleware = HillClimbingMiddleware(iterations=50, seed=42)

        # Run
        new_schedule = middleware.map_result(problem, schedule)

        # Verify improvement
        # Expected: One task on Team 0, one on Team 1. Makespan 10.

        makespan = 0
        assigned_teams = []
        for a in new_schedule.assignments:
            finish = a.start_time + 10
            if finish > makespan:
                makespan = finish
            assigned_teams.append(a.team_id)

        self.assertLess(makespan, 20)
        self.assertEqual(makespan, 10)
        self.assertNotEqual(assigned_teams[0], assigned_teams[1])

    def test_dependency_preservation(self):
        # Task 0 -> Task 1
        tasks = {
            0: Task(0, 10, [], [], {0: 10}),
            1: Task(1, 10, [0], [], {0: 10}),
        }
        teams = {
            0: Team(0, 0),
        }
        problem = ProblemInstance(2, 1, tasks, teams)

        assignments = [
            Assignment(0, 0, 0),
            Assignment(1, 0, 10),
        ]
        schedule = Schedule(assignments)

        middleware = HillClimbingMiddleware(iterations=10, seed=42)
        new_schedule = middleware.map_result(problem, schedule)

        # Check validity
        times = {
            a.task_id: (a.start_time, a.start_time + 10)
            for a in new_schedule.assignments
        }
        t0_end = times[0][1]
        t1_start = times[1][0]

        self.assertGreaterEqual(t1_start, t0_end)


if __name__ == "__main__":
    unittest.main()
