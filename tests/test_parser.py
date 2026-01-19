import unittest
from io import StringIO
from paas.parser import parse_input, parse_solution


class TestParser(unittest.TestCase):
    def test_example_parsing(self):
        input_data = """5 4
1 2
1 4
2 5
3 5
60 45 120 150 20
6
100 20 65 40 25 90
13
1 4 20
1 5 30
1 6 10
2 2 25
2 5 30
3 1 20
3 6 70
4 2 10
4 3 10
4 5 20
5 1 40
5 2 20
5 5 10
"""
        problem = parse_input(StringIO(input_data))

        self.assertEqual(problem.num_tasks, 5)
        self.assertEqual(problem.num_teams, 6)

        # Check task 1
        t1 = problem.tasks[1]
        self.assertEqual(t1.duration, 60)
        self.assertEqual(t1.successors, [2, 4])
        self.assertEqual(t1.compatible_teams, {4: 20, 5: 30, 6: 10})

        # Check task 5
        t5 = problem.tasks[5]
        self.assertEqual(t5.duration, 20)
        self.assertEqual(sorted(t5.predecessors), [2, 3])
        self.assertEqual(t5.compatible_teams, {1: 40, 2: 20, 5: 10})

        # Check teams
        self.assertEqual(problem.teams[1].available_from, 100)
        self.assertEqual(problem.teams[6].available_from, 90)

    def test_parse_solution(self):
        solution_data = """3
1 2 100
2 3 150
3 1 200
"""
        schedule = parse_solution(StringIO(solution_data))

        self.assertEqual(len(schedule.assignments), 3)

        a1 = schedule.assignments[0]
        self.assertEqual(a1.task_id, 1)
        self.assertEqual(a1.team_id, 2)
        self.assertEqual(a1.start_time, 100)

        a2 = schedule.assignments[1]
        self.assertEqual(a2.task_id, 2)
        self.assertEqual(a2.team_id, 3)
        self.assertEqual(a2.start_time, 150)

        a3 = schedule.assignments[2]
        self.assertEqual(a3.task_id, 3)
        self.assertEqual(a3.team_id, 1)
        self.assertEqual(a3.start_time, 200)


if __name__ == "__main__":
    unittest.main()
