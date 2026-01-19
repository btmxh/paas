import unittest
import time
from paas.models import Task, ProblemInstance, Schedule, Team, Assignment
from paas.middleware.simulated_annealing import SimulatedAnnealingRefiner


class TestSimulatedAnnealing(unittest.TestCase):
    def test_time_limit_respected(self):
        # Create a dummy problem
        # Make it slightly complex so it doesn't just finish instantly if we were to optimize strictly
        # But SA continues until time/iter limit anyway.
        tasks = {}
        for i in range(1, 20):
            tasks[i] = Task(i, 10, [], [], {1: 10, 2: 20})

        teams = {1: Team(1, 0), 2: Team(2, 0)}
        problem = ProblemInstance(len(tasks), 2, tasks, teams)

        # Initial schedule (empty or partial doesn't matter much for this test)
        schedule = Schedule([])

        sa = SimulatedAnnealingRefiner(max_iterations=100000000)  # Huge iterations

        start = time.time()
        # Run for 0.2 seconds
        # The overhead of SA init is small, so it should be close to 0.2
        sa.map_result(problem, schedule, time_limit=0.2)
        end = time.time()

        duration = end - start
        print(f"SA Duration: {duration}")
        # Allow some overhead, but it shouldn't be much larger than 0.2 + overhead
        # Python execution can be jittery, giving it 0.5s margin
        self.assertLess(duration, 0.7)
        # It should at least respect the time limit (approx), not stop immediately
        # But if it does one iteration and that takes < 0.2s, it continues.
        self.assertGreater(duration, 0.15)

    def test_max_iterations_fallback(self):
        # Test fallback when time_limit is inf
        t1 = Task(1, 10, [], [], {1: 10})
        tasks = {1: t1}
        teams = {1: Team(1, 0)}
        problem = ProblemInstance(1, 1, tasks, teams)
        schedule = Schedule([Assignment(1, 1, 0)])

        # 10 iterations should be super fast
        sa = SimulatedAnnealingRefiner(max_iterations=10)

        start = time.time()
        sa.map_result(problem, schedule, time_limit=float("inf"))
        end = time.time()

        duration = end - start
        # Should be very fast
        self.assertLess(duration, 0.5)


if __name__ == "__main__":
    unittest.main()
