import unittest
from paas.models import Task, Team, ProblemInstance
from paas.solvers.greedy_min_start_time import GreedyMinStartTimeSolver


class TestGreedyMinStartTimeSolver(unittest.TestCase):
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

        solver = GreedyMinStartTimeSolver()
        schedule = solver.run(problem)

        # Expect all tasks to be scheduled
        self.assertEqual(len(schedule.assignments), 3)

        # Verify assignments map
        assign_map = {a.task_id: a for a in schedule.assignments}

        a1 = assign_map[1]
        a2 = assign_map[2]
        a3 = assign_map[3]

        # 1 and 2 should start at 0 (roots)
        self.assertEqual(a1.start_time, 0)
        self.assertEqual(a2.start_time, 0)

        # 1 should prefer T1 (cost 10 < 20), 2 should prefer T2 (cost 10 < 20)
        # Assuming eager root scheduling works as expected
        self.assertEqual(a1.team_id, 1)
        self.assertEqual(a2.team_id, 2)

        # 3 must start after max(1, 2) finish.
        # 1 finishes at 0+10=10. 2 finishes at 0+10=10.
        # 3 starts at 10.
        self.assertGreaterEqual(a3.start_time, 10)

        # Check team availability update implicit logic
        # T1 finishes 1 at 10. T2 finishes 2 at 10.
        # 3 can use either T1 or T2 starting at 10.
        self.assertEqual(a3.start_time, 10)

    def test_dependencies(self):
        # 1 -> 2
        # T1 avail 0
        t1 = Task(id=1, duration=10, successors=[2], compatible_teams={1: 10})
        t2 = Task(id=2, duration=10, predecessors=[1], compatible_teams={1: 10})

        tasks = {1: t1, 2: t2}
        teams = {1: Team(id=1, available_from=0)}
        problem = ProblemInstance(2, 1, tasks, teams)

        solver = GreedyMinStartTimeSolver()
        schedule = solver.run(problem)

        assign_map = {a.task_id: a for a in schedule.assignments}

        self.assertEqual(assign_map[1].start_time, 0)
        self.assertEqual(assign_map[2].start_time, 10)
        self.assertEqual(assign_map[1].team_id, 1)
        self.assertEqual(assign_map[2].team_id, 1)


if __name__ == "__main__":
    unittest.main()
