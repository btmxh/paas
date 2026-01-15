import unittest
from paas.middleware.base import Pipeline, Middleware, Solver
from paas.models import ProblemInstance, Schedule
from paas.time_budget import TimeBudget


class SpySolver(Solver):
    def __init__(self, time_factor=1.0):
        super().__init__(time_factor)
        self.last_time_limit = float("nan")

    def run(self, problem, time_limit=float("inf")):
        self.last_time_limit = time_limit
        return Schedule([])


class SpyMiddleware(Middleware):
    def __init__(self, time_factor=1.0):
        super().__init__(time_factor)
        self.last_time_limit = float("nan")

    def run(self, problem, next_runnable, time_limit=float("inf")):
        self.last_time_limit = time_limit
        return next_runnable.run(problem, time_limit=time_limit)


class TestPipelineBudget(unittest.TestCase):
    def test_budget_distribution(self):
        m1 = SpyMiddleware(time_factor=1.0)
        m2 = SpyMiddleware(time_factor=2.0)
        solver = SpySolver(time_factor=2.0)

        # Total factor = 1 + 2 + 2 = 5
        # Total budget = 10s
        # m1 gets 2s, m2 gets 4s, solver gets 4s

        pipeline = Pipeline(
            middlewares=[m1, m2],
            solver=solver,
            total_budget=TimeBudget.from_seconds(10.0),
        )

        problem = ProblemInstance(0, 0, {}, {})
        pipeline.run(problem)

        self.assertAlmostEqual(m1.last_time_limit, 2.0)
        self.assertAlmostEqual(m2.last_time_limit, 4.0)
        self.assertAlmostEqual(solver.last_time_limit, 4.0)

    def test_budget_distribution_default_solver(self):
        m1 = SpyMiddleware(time_factor=1.0)
        # Solver with default time_factor (1.0)
        solver = SpySolver()

        # Total factor = 1.0 + 1.0 = 2.0
        # Budget = 10s => m1 gets 5s

        pipeline = Pipeline(
            middlewares=[m1], solver=solver, total_budget=TimeBudget.from_seconds(10.0)
        )

        problem = ProblemInstance(0, 0, {}, {})
        pipeline.run(problem)

        self.assertAlmostEqual(m1.last_time_limit, 5.0)
        self.assertAlmostEqual(solver.last_time_limit, 5.0)


if __name__ == "__main__":
    unittest.main()
