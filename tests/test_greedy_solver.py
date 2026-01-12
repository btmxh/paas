import unittest
from paas.models import Task, Team, ProblemInstance
from paas.solvers.greedy_solver import GreedySolver


class TestGreedySolver(unittest.TestCase):
    def test_example_scenario(self):
        # Teams
        teams = {
            1: Team(id=1, available_from=100),
            2: Team(id=2, available_from=20),
            3: Team(id=3, available_from=65),
            4: Team(id=4, available_from=40),
            5: Team(id=5, available_from=25),
            6: Team(id=6, available_from=90),
        }

        # Tasks
        # 1: 60. Compat: 4(20), 5(30), 6(10). Preds: [], Succs: [2, 4]
        t1 = Task(
            id=1,
            duration=60,
            predecessors=[],
            successors=[2, 4],
            compatible_teams={4: 20, 5: 30, 6: 10},
        )

        # 2: 45. Compat: 2(25), 5(30). Preds: [1], Succs: [5]
        t2 = Task(
            id=2,
            duration=45,
            predecessors=[1],
            successors=[5],
            compatible_teams={2: 25, 5: 30},
        )

        # 3: 120. Compat: 1(20), 6(70). Preds: [], Succs: [5]
        t3 = Task(
            id=3,
            duration=120,
            predecessors=[],
            successors=[5],
            compatible_teams={1: 20, 6: 70},
        )

        # 4: 150. Compat: 2(10), 3(10), 5(20). Preds: [1], Succs: []
        t4 = Task(
            id=4,
            duration=150,
            predecessors=[1],
            successors=[],
            compatible_teams={2: 10, 3: 10, 5: 20},
        )

        # 5: 20. Compat: 1(40), 2(20), 5(10). Preds: [2, 3], Succs: []
        t5 = Task(
            id=5,
            duration=20,
            predecessors=[2, 3],
            successors=[],
            compatible_teams={1: 40, 2: 20, 5: 10},
        )

        tasks = {1: t1, 2: t2, 3: t3, 4: t4, 5: t5}

        instance = ProblemInstance(num_tasks=5, num_teams=6, tasks=tasks, teams=teams)

        solver = GreedySolver()
        schedule = solver.solve(instance)

        # Verify assignments
        assignments_map = {a.task_id: a for a in schedule.assignments}

        self.assertEqual(len(assignments_map), 5)

        # Based on manual trace
        # Task 1: Team 5, Start 25
        self.assertEqual(assignments_map[1].team_id, 5)
        self.assertEqual(assignments_map[1].start_time, 25)

        # Task 2: Team 2, Start 85
        self.assertEqual(assignments_map[2].team_id, 2)
        self.assertEqual(assignments_map[2].start_time, 85)

        # Task 3: Team 6, Start 90
        self.assertEqual(assignments_map[3].team_id, 6)
        self.assertEqual(assignments_map[3].start_time, 90)

        # Task 4: Team 3, Start 85
        self.assertEqual(assignments_map[4].team_id, 3)
        self.assertEqual(assignments_map[4].start_time, 85)

        # Task 5: Team 5, Start 210
        self.assertEqual(assignments_map[5].team_id, 5)
        self.assertEqual(assignments_map[5].start_time, 210)

    def test_impossible_task(self):
        # Task with no compatible teams
        teams = {1: Team(id=1, available_from=0)}
        t1 = Task(id=1, duration=10, compatible_teams={})

        instance = ProblemInstance(num_tasks=1, num_teams=1, tasks={1: t1}, teams=teams)

        solver = GreedySolver()
        schedule = solver.solve(instance)

        self.assertEqual(len(schedule.assignments), 0)


if __name__ == "__main__":
    unittest.main()
