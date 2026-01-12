import unittest
from paas.models import Task, ProblemInstance, Team
from paas.solvers.cp_solver import CPSolver


class TestCPSolver(unittest.TestCase):
    def setUp(self):
        self.solver = CPSolver()

    def test_single_task(self):
        tasks = {
            1: Task(
                id=1,
                duration=5,
                predecessors=[],
                successors=[],
                compatible_teams={1: 10},
            )
        }
        teams = {1: Team(id=1, available_from=0)}
        problem = ProblemInstance(num_tasks=1, num_teams=1, tasks=tasks, teams=teams)

        schedule = self.solver.run(problem)

        self.assertEqual(len(schedule.assignments), 1)
        assignment = schedule.assignments[0]
        self.assertEqual(assignment.task_id, 1)
        self.assertEqual(assignment.team_id, 1)
        self.assertEqual(assignment.start_time, 0)

    def test_precedence(self):
        tasks = {
            1: Task(
                id=1,
                duration=5,
                predecessors=[],
                successors=[2],
                compatible_teams={1: 10},
            ),
            2: Task(
                id=2,
                duration=3,
                predecessors=[1],
                successors=[],
                compatible_teams={1: 10},
            ),
        }
        teams = {1: Team(id=1, available_from=0)}
        problem = ProblemInstance(num_tasks=2, num_teams=1, tasks=tasks, teams=teams)

        schedule = self.solver.run(problem)

        self.assertEqual(len(schedule.assignments), 2)

        # Sort assignments by task_id for easier checking
        assignments = {a.task_id: a for a in schedule.assignments}

        self.assertEqual(assignments[1].start_time, 0)
        self.assertGreaterEqual(assignments[2].start_time, 5)

    def test_resource_constraint(self):
        # Two tasks, same team, but no precedence. They must be sequential.
        tasks = {
            1: Task(
                id=1,
                duration=5,
                predecessors=[],
                successors=[],
                compatible_teams={1: 10},
            ),
            2: Task(
                id=2,
                duration=5,
                predecessors=[],
                successors=[],
                compatible_teams={1: 10},
            ),
        }
        teams = {1: Team(id=1, available_from=0)}
        problem = ProblemInstance(num_tasks=2, num_teams=1, tasks=tasks, teams=teams)

        schedule = self.solver.run(problem)

        self.assertEqual(len(schedule.assignments), 2)
        a1 = next(a for a in schedule.assignments if a.task_id == 1)
        a2 = next(a for a in schedule.assignments if a.task_id == 2)

        # One must start after the other ends
        if a1.start_time < a2.start_time:
            self.assertGreaterEqual(a2.start_time, a1.start_time + 5)
        else:
            self.assertGreaterEqual(a1.start_time, a2.start_time + 5)

    def test_team_availability(self):
        tasks = {
            1: Task(
                id=1,
                duration=5,
                predecessors=[],
                successors=[],
                compatible_teams={1: 10},
            )
        }
        teams = {1: Team(id=1, available_from=10)}
        problem = ProblemInstance(num_tasks=1, num_teams=1, tasks=tasks, teams=teams)

        schedule = self.solver.run(problem)

        self.assertEqual(len(schedule.assignments), 1)
        self.assertGreaterEqual(schedule.assignments[0].start_time, 10)

    def test_optimization_cost(self):
        # Two teams, different costs. Should pick cheaper one.
        tasks = {
            1: Task(
                id=1,
                duration=5,
                predecessors=[],
                successors=[],
                compatible_teams={1: 100, 2: 10},
            )
        }
        teams = {1: Team(id=1, available_from=0), 2: Team(id=2, available_from=0)}
        problem = ProblemInstance(num_tasks=1, num_teams=2, tasks=tasks, teams=teams)

        schedule = self.solver.run(problem)

        self.assertEqual(len(schedule.assignments), 1)
        self.assertEqual(schedule.assignments[0].team_id, 2)

    def test_optimization_makespan(self):
        # Two tasks, duration 10. Two teams.
        # Cost is same for both teams.
        # To minimize makespan, they should be scheduled in parallel on different teams.
        tasks = {
            1: Task(
                id=1,
                duration=10,
                predecessors=[],
                successors=[],
                compatible_teams={1: 10, 2: 10},
            ),
            2: Task(
                id=2,
                duration=10,
                predecessors=[],
                successors=[],
                compatible_teams={1: 10, 2: 10},
            ),
        }
        teams = {1: Team(id=1, available_from=0), 2: Team(id=2, available_from=0)}
        problem = ProblemInstance(num_tasks=2, num_teams=2, tasks=tasks, teams=teams)

        schedule = self.solver.run(problem)

        self.assertEqual(len(schedule.assignments), 2)
        a1 = next(a for a in schedule.assignments if a.task_id == 1)
        a2 = next(a for a in schedule.assignments if a.task_id == 2)

        self.assertEqual(a1.start_time, 0)
        self.assertEqual(a2.start_time, 0)
        self.assertNotEqual(a1.team_id, a2.team_id)

    def test_empty_problem(self):
        problem = ProblemInstance(num_tasks=0, num_teams=0, tasks={}, teams={})
        schedule = self.solver.run(problem)
        self.assertEqual(len(schedule.assignments), 0)


if __name__ == "__main__":
    unittest.main()
