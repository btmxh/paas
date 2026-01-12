import unittest
from paas.models import Task, ProblemInstance
from paas.middleware.cycle_remover import CycleRemover
from paas.middleware.impossible_task_remover import ImpossibleTaskRemover
from paas.middleware.dependency_pruner import DependencyPruner


class TestMiddlewarePipeline(unittest.TestCase):
    def create_task(
        self, tid, duration=10, preds=None, succs=None, compatible_teams=None
    ):
        if preds is None:
            preds = []
        if succs is None:
            succs = []
        if compatible_teams is None:
            compatible_teams = {1: 10}  # Default one team
        return Task(tid, duration, preds, succs, compatible_teams)

    def test_pipeline_integration(self):
        # Scenario:
        # Cycle: 1 <-> 2
        # Dependent on Cycle: 3 (depends on 2)
        # No Teams: 4
        # Dependent on No Teams: 5 (depends on 4)
        # Chain: 6 -> 7

        t1 = self.create_task(1, succs=[2], preds=[2])
        t2 = self.create_task(2, succs=[1, 3], preds=[1])
        t3 = self.create_task(3, preds=[2])

        t4 = self.create_task(4, compatible_teams={}, succs=[5])
        t5 = self.create_task(5, preds=[4])

        t6 = self.create_task(6, succs=[7])
        t7 = self.create_task(7, preds=[6])

        tasks = {1: t1, 2: t2, 3: t3, 4: t4, 5: t5, 6: t6, 7: t7}
        # Teams don't really matter for structure, just count
        teams = {1: "Team1"}  # Mock team object

        problem = ProblemInstance(7, 1, tasks, teams)

        # 1. Run CycleRemover
        cycle_remover = CycleRemover()
        p1 = cycle_remover.map_problem(problem)

        # Expect 1 and 2 removed. 3 remains but invalid.
        self.assertNotIn(1, p1.tasks)
        self.assertNotIn(2, p1.tasks)
        self.assertIn(3, p1.tasks)
        self.assertIn(4, p1.tasks)  # Still there
        self.assertIn(5, p1.tasks)

        # 2. Run ImpossibleTaskRemover
        impossible_remover = ImpossibleTaskRemover()
        p2 = impossible_remover.map_problem(p1)

        # Expect 4 removed. 5 remains but invalid.
        self.assertNotIn(4, p2.tasks)
        self.assertIn(5, p2.tasks)
        self.assertIn(3, p2.tasks)

        # 3. Run DependencyPruner
        dependency_pruner = DependencyPruner()
        p3 = dependency_pruner.map_problem(p2)

        # Expect 3 removed (depended on 2).
        # Expect 5 removed (depended on 4).
        # Expect 6, 7 to remain.
        self.assertNotIn(3, p3.tasks)
        self.assertNotIn(5, p3.tasks)
        self.assertIn(6, p3.tasks)
        self.assertIn(7, p3.tasks)

        # Verify 6's successors and 7's predecessors are clean
        self.assertEqual(p3.tasks[6].successors, [7])
        self.assertEqual(p3.tasks[7].predecessors, [6])


if __name__ == "__main__":
    unittest.main()
