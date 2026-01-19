import unittest
import time
from paas.models import Task, ProblemInstance, Schedule, Team
from paas.middleware.simulated_annealing import SimulatedAnnealingRefiner


class TestSimulatedAnnealing(unittest.TestCase):
    def test_time_limit_respected(self):
        # Create a dummy problem
        tasks = {}
        for i in range(1, 20):
            tasks[i] = Task(i, 10, [], [], {1: 10, 2: 20})

        teams = {1: Team(1, 0), 2: Team(2, 0)}
        problem = ProblemInstance(len(tasks), 2, tasks, teams)

        # Initial schedule
        schedule = Schedule([])

        # Initialize without max_iterations
        sa = SimulatedAnnealingRefiner()

        start = time.time()
        # Run for 0.2 seconds
        sa.map_result(problem, schedule, time_limit=0.2)
        end = time.time()

        duration = end - start
        print(f"SA Duration: {duration}")

        # Verify it respected the time limit reasonably well
        self.assertLess(duration, 0.7)
        self.assertGreater(duration, 0.15)


if __name__ == "__main__":
    unittest.main()
