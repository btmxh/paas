import unittest
from paas.models import Task, Team, ProblemInstance
from paas.solvers.random_solver import RandomSolver


class TestRandomSolver(unittest.TestCase):
    def test_simple_schedule(self):
        # 3 tasks
        # 1 -> 3
        # 2 -> 3
        # Teams: T1 (avail 0), T2 (avail 0)

        t1 = Task(id=1, duration=10, successors=[3], compatible_teams={1: 10, 2: 20})
        t2 = Task(id=2, duration=10, successors=[3], compatible_teams={1: 20, 2: 10})
        t3 = Task(
            id=3, duration=10, predecessors=[1, 2], compatible_teams={1: 10, 2: 10}
        )

        tasks = {1: t1, 2: t2, 3: t3}
        teams = {1: Team(id=1, available_from=0), 2: Team(id=2, available_from=0)}

        problem = ProblemInstance(num_tasks=3, num_teams=2, tasks=tasks, teams=teams)

        # Use seed for reproducibility if needed, but we check validity generally
        solver = RandomSolver(seed=42)
        schedule = solver.run(problem)

        # Expect all tasks to be scheduled
        self.assertEqual(len(schedule.assignments), 3)

        # Verify assignments map
        assign_map = {a.task_id: a for a in schedule.assignments}
        a1 = assign_map[1]
        a2 = assign_map[2]
        a3 = assign_map[3]

        # Check dependencies
        # 3 must start after 1 and 2 finish
        finish1 = a1.start_time + 10
        finish2 = a2.start_time + 10
        self.assertGreaterEqual(a3.start_time, finish1)
        self.assertGreaterEqual(a3.start_time, finish2)

    def test_dependencies_chain(self):
        # 1 -> 2 -> 3
        # T1 avail 0
        t1 = Task(id=1, duration=10, successors=[2], compatible_teams={1: 10})
        t2 = Task(
            id=2,
            duration=10,
            predecessors=[1],
            successors=[3],
            compatible_teams={1: 10},
        )
        t3 = Task(id=3, duration=10, predecessors=[2], compatible_teams={1: 10})

        tasks = {1: t1, 2: t2, 3: t3}
        teams = {1: Team(id=1, available_from=0)}
        problem = ProblemInstance(3, 1, tasks, teams)

        solver = RandomSolver(seed=123)
        schedule = solver.run(problem)

        self.assertEqual(len(schedule.assignments), 3)
        assign_map = {a.task_id: a for a in schedule.assignments}

        # Check sequential execution on same team
        # 1 starts >= 0
        # 2 starts >= 1 finish
        # 3 starts >= 2 finish
        self.assertGreaterEqual(assign_map[2].start_time, assign_map[1].start_time + 10)
        self.assertGreaterEqual(assign_map[3].start_time, assign_map[2].start_time + 10)


if __name__ == "__main__":
    unittest.main()
