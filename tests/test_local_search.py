import unittest
from paas.models import Task, Team, ProblemInstance, Schedule, Assignment
from paas.middleware.local_search import LocalSearchMiddleware


class TestLocalSearchMiddleware(unittest.TestCase):
    def setUp(self):
        # Task 1: dur 10, Team 1 (cost 100), Team 2 (cost 50)
        self.t1 = Task(1, 10, [], [], {1: 100, 2: 50})
        # Team 1 available from 0, Team 2 available from 0
        self.team1 = Team(1, 0)
        self.team2 = Team(2, 0)

        self.instance = ProblemInstance(
            num_tasks=1,
            num_teams=2,
            tasks={1: self.t1},
            teams={1: self.team1, 2: self.team2},
        )

    def test_basic_improvement(self):
        # Initial: Task 1 on Team 1 (cost 100)
        initial_schedule = Schedule(assignments=[Assignment(1, 1, 0)])

        middleware = LocalSearchMiddleware()
        refined_schedule = middleware.map_result(self.instance, initial_schedule)

        # Should move to Team 2 (cost 50)
        self.assertEqual(len(refined_schedule.assignments), 1)
        self.assertEqual(refined_schedule.assignments[0].team_id, 2)
        self.assertEqual(refined_schedule.assignments[0].start_time, 0)

    def test_precedence_constraint_honored(self):
        # Task 1: dur 10, Team 1 (100), Team 2 (50)
        # Task 2: dur 10, Team 1 (100), Team 2 (50), depends on Task 1
        t1 = Task(1, 10, [], [2], {1: 100, 2: 50})
        t2 = Task(2, 10, [1], [], {1: 100, 2: 50})

        instance = ProblemInstance(
            num_tasks=2,
            num_teams=2,
            tasks={1: t1, 2: t2},
            teams={1: self.team1, 2: self.team2},
        )

        # Initial:
        # T1 on Team 1 at 0 (ends 10)
        # T2 on Team 1 at 10 (ends 20)
        # Makespan: 20, Cost: 200
        initial_schedule = Schedule(
            assignments=[Assignment(1, 1, 0), Assignment(2, 1, 10)]
        )

        middleware = LocalSearchMiddleware()
        refined_schedule = middleware.map_result(instance, initial_schedule)

        # Should move both to Team 2
        # T1 on Team 2 at 0 (ends 10)
        # T2 on Team 2 at 10 (ends 20)
        # Makespan: 20, Cost: 100
        costs = {
            a.task_id: instance.tasks[a.task_id].compatible_teams[a.team_id]
            for a in refined_schedule.assignments
        }
        self.assertEqual(sum(costs.values()), 100)

        # Verify precedence
        assign_map = {a.task_id: a for a in refined_schedule.assignments}
        self.assertGreaterEqual(assign_map[2].start_time, assign_map[1].start_time + 10)

    def test_makespan_constraint(self):
        # Task 1: dur 10, Team 1 (100), Team 2 (50)
        # Team 2 is only available from 10
        team2_late = Team(2, 10)

        instance = ProblemInstance(
            num_tasks=1,
            num_teams=2,
            tasks={1: self.t1},
            teams={1: self.team1, 2: team2_late},
        )

        # Initial: T1 on Team 1 at 0 (ends 10). Makespan 10.
        initial_schedule = Schedule(assignments=[Assignment(1, 1, 0)])

        middleware = LocalSearchMiddleware()
        refined_schedule = middleware.map_result(instance, initial_schedule)

        # Should NOT move to Team 2 because it would increase makespan to 20
        self.assertEqual(refined_schedule.assignments[0].team_id, 1)
