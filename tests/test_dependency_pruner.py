import unittest
from paas.models import Task, ProblemInstance
from paas.middleware.dependency_pruner import DependencyPruner


class TestDependencyPruner(unittest.TestCase):
    def create_task(self, tid, preds=None, succs=None):
        return Task(tid, 10, preds or [], succs or [], {1: 10})

    def test_prune_broken_predecessor(self):
        # 1 -> 2 -> 3
        # If 1 is missing, 2 and 3 should be pruned.
        t2 = self.create_task(2, preds=[1], succs=[3])
        t3 = self.create_task(3, preds=[2])

        # Note: Task 1 is NOT in the dictionary
        tasks = {2: t2, 3: t3}
        problem = ProblemInstance(2, 1, tasks, {})

        pruner = DependencyPruner()
        new_problem = pruner.map_problem(problem)

        self.assertEqual(len(new_problem.tasks), 0)

    def test_cleanup_stale_references(self):
        # 1 -> 2
        # If 2 is missing, 1 should remain but its successors list should be empty.
        t1 = self.create_task(1, succs=[2])

        tasks = {1: t1}
        problem = ProblemInstance(1, 1, tasks, {})

        pruner = DependencyPruner()
        new_problem = pruner.map_problem(problem)

        self.assertIn(1, new_problem.tasks)
        self.assertEqual(new_problem.tasks[1].successors, [])

    def test_transitive_pruning(self):
        # 1 (exists)
        # 2 (missing) -> 3 -> 4
        # 5 (exists)
        t1 = self.create_task(1)
        t3 = self.create_task(3, preds=[2], succs=[4])
        t4 = self.create_task(4, preds=[3])
        t5 = self.create_task(5)

        tasks = {1: t1, 3: t3, 4: t4, 5: t5}
        problem = ProblemInstance(4, 1, tasks, {})

        pruner = DependencyPruner()
        new_problem = pruner.map_problem(problem)

        self.assertIn(1, new_problem.tasks)
        self.assertIn(5, new_problem.tasks)
        self.assertNotIn(3, new_problem.tasks)
        self.assertNotIn(4, new_problem.tasks)
