import unittest
from paas.models import ProblemInstance, Task, Team, Schedule, Assignment
from paas.middleware.pso_search import PSOSearchMiddleware
from paas.middleware.aco_search import ACOSearchMiddleware


class TestPSOCOMiddleware(unittest.TestCase):
    def setUp(self):
        # Create a simple problem
        tasks = {
            1: Task(id=1, duration=10, successors=[2], compatible_teams={1: 10}),
            2: Task(id=2, duration=20, predecessors=[1], compatible_teams={1: 20}),
        }
        teams = {1: Team(id=1, available_from=0)}
        self.problem = ProblemInstance(
            num_tasks=2, num_teams=1, tasks=tasks, teams=teams
        )

        # Create a seed schedule
        self.seed = Schedule(
            assignments=[
                Assignment(task_id=1, team_id=1, start_time=0),
                Assignment(task_id=2, team_id=1, start_time=10),
            ]
        )

    def test_pso_middleware_with_seed(self):
        middleware = PSOSearchMiddleware(swarm_size=5, max_iterations=20)
        result = middleware.map_result(self.problem, self.seed)
        self.assertEqual(len(result.assignments), 2)
        # Verify it remains valid
        self.assertTrue(any(a.task_id == 1 for a in result.assignments))
        self.assertTrue(any(a.task_id == 2 for a in result.assignments))

    def test_aco_middleware_with_seed(self):
        middleware = ACOSearchMiddleware(num_ants=5, iterations=2)
        result = middleware.map_result(self.problem, self.seed)
        self.assertEqual(len(result.assignments), 2)
        self.assertTrue(any(a.task_id == 1 for a in result.assignments))
        self.assertTrue(any(a.task_id == 2 for a in result.assignments))


if __name__ == "__main__":
    unittest.main()
