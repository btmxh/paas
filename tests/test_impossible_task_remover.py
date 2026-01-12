import unittest
from paas.models import Task, ProblemInstance
from paas.middleware.impossible_task_remover import ImpossibleTaskRemover


class TestImpossibleTaskRemover(unittest.TestCase):
    def create_task(self, tid, compatible_teams=None):
        if compatible_teams is None:
            compatible_teams = {1: 10}
        return Task(tid, 10, [], [], compatible_teams)

    def test_remove_impossible_tasks(self):
        # T1 is possible, T2 is impossible, T3 is possible
        t1 = self.create_task(1, {1: 10})
        t2 = self.create_task(2, {})
        t3 = self.create_task(3, {2: 5})

        tasks = {1: t1, 2: t2, 3: t3}
        problem = ProblemInstance(3, 2, tasks, {})

        remover = ImpossibleTaskRemover()
        new_problem = remover.map_problem(problem)

        self.assertIn(1, new_problem.tasks)
        self.assertNotIn(2, new_problem.tasks)
        self.assertIn(3, new_problem.tasks)
        self.assertEqual(len(new_problem.tasks), 2)

    def test_no_impossible_tasks(self):
        t1 = self.create_task(1, {1: 10})
        tasks = {1: t1}
        problem = ProblemInstance(1, 1, tasks, {})

        remover = ImpossibleTaskRemover()
        new_problem = remover.map_problem(problem)

        self.assertEqual(len(new_problem.tasks), 1)
        self.assertIs(new_problem, problem)  # Should return original if no changes
