import unittest
from paas.models import Task, ProblemInstance
from paas.middleware.cycle_remover import CycleRemover


class TestCycleRemover(unittest.TestCase):
    def create_task(self, tid, duration=10, preds=None, succs=None):
        if preds is None:
            preds = []
        if succs is None:
            succs = []
        return Task(tid, duration, preds, succs, {})

    def test_cycle_removal_only(self):
        # Scenario:
        # 1 -> 2
        # 2 -> 3
        # 3 -> 2 (Cycle 2-3)
        # 3 -> 4
        # 5 (Independent)
        # 6 -> 6 (Self-loop)

        t1 = self.create_task(1, succs=[2])
        t2 = self.create_task(2, preds=[1], succs=[3])
        t3 = self.create_task(3, preds=[2], succs=[2, 4])
        t4 = self.create_task(4, preds=[3])
        t5 = self.create_task(5)
        t6 = self.create_task(6, succs=[6])

        tasks = {1: t1, 2: t2, 3: t3, 4: t4, 5: t5, 6: t6}
        teams = {}

        problem = ProblemInstance(6, 0, tasks, teams)

        remover = CycleRemover()
        new_problem = remover.map_problem(problem)

        # Assertions
        self.assertNotIn(2, new_problem.tasks, "Task 2 (in cycle) should be removed")
        self.assertNotIn(3, new_problem.tasks, "Task 3 (in cycle) should be removed")
        self.assertNotIn(6, new_problem.tasks, "Task 6 (self-loop) should be removed")

        # UPDATED BEHAVIOR: Dependents are NOT removed by CycleRemover alone
        self.assertIn(
            4,
            new_problem.tasks,
            "Task 4 (depends on cycle) should NOT be removed by CycleRemover",
        )
        self.assertIn(1, new_problem.tasks, "Task 1 (precedes cycle) should be kept")
        self.assertIn(5, new_problem.tasks, "Task 5 (independent) should be kept")

        # UPDATED BEHAVIOR: Adjacency lists are NOT cleaned up by CycleRemover
        # Task 1 still points to 2, even though 2 is gone.
        t1_new = new_problem.tasks[1]
        self.assertIn(
            2, t1_new.successors, "Task 1 should still have stale reference to 2"
        )

        # Task 4 still points from 3
        t4_new = new_problem.tasks[4]
        self.assertIn(
            3, t4_new.predecessors, "Task 4 should still have stale reference to 3"
        )


if __name__ == "__main__":
    unittest.main()
