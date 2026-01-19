import unittest
from paas.models import Task, Team, ProblemInstance
from paas.solvers.ga_solver import GASolver


class TestGASolver(unittest.TestCase):
    def test_simple_schedule(self):
        # 3 tasks
        # 0 -> 2
        # 1 -> 2
        # Teams: T1 (avail 0), T2 (avail 0)

        t1 = Task(id=0, duration=10, successors=[2], compatible_teams={1: 10, 2: 20})
        t2 = Task(id=1, duration=10, successors=[2], compatible_teams={1: 20, 2: 10})
        t3 = Task(
            id=2, duration=10, predecessors=[0, 1], compatible_teams={1: 10, 2: 10}
        )

        tasks = {0: t1, 1: t2, 2: t3}
        teams = {1: Team(id=1, available_from=0), 2: Team(id=2, available_from=0)}

        problem = ProblemInstance(num_tasks=3, num_teams=2, tasks=tasks, teams=teams)

        solver = GASolver(
            initial_population_size=5, max_population_size=10, max_generation=10
        )
        schedule = solver.run(problem)

        # Expect all tasks to be scheduled
        self.assertEqual(len(schedule.assignments), 3)

        # Verify assignments map
        assign_map = {a.task_id: a for a in schedule.assignments}

        a1 = assign_map[0]
        a2 = assign_map[1]
        a3 = assign_map[2]

        # 2 must start after max(0, 1) finish.
        self.assertGreaterEqual(a3.start_time, a1.start_time + tasks[0].duration)
        self.assertGreaterEqual(a3.start_time, a2.start_time + tasks[1].duration)

    def test_dependencies(self):
        # 0 -> 1
        # T1 avail 0
        t1 = Task(id=0, duration=10, successors=[1], compatible_teams={1: 10})
        t2 = Task(id=1, duration=10, predecessors=[0], compatible_teams={1: 10})

        tasks = {0: t1, 1: t2}
        teams = {1: Team(id=1, available_from=0)}
        problem = ProblemInstance(2, 1, tasks, teams)

        solver = GASolver(
            initial_population_size=5, max_population_size=10, max_generation=10
        )
        schedule = solver.run(problem)

        assign_map = {a.task_id: a for a in schedule.assignments}

        self.assertEqual(len(schedule.assignments), 2)
        self.assertEqual(assign_map[0].start_time, 0)
        self.assertEqual(assign_map[1].start_time, 10)


if __name__ == "__main__":
    unittest.main()
