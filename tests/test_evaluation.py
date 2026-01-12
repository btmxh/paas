import unittest
from paas.models import Task, Team, ProblemInstance, Schedule, Assignment
from paas.checker import validate_schedule
from paas.grader import grade_schedule, Score


class TestEvaluation(unittest.TestCase):
    def setUp(self):
        # Basic setup: 2 tasks, 2 teams
        # Task 1: dur 10, compatible with Team 1 (cost 5) and Team 2 (cost 10)
        # Task 2: dur 20, compatible with Team 1 (cost 15), depends on Task 1
        self.t1 = Task(1, 10, [], [2], {1: 5, 2: 10})
        self.t2 = Task(2, 20, [1], [], {1: 15})
        self.team1 = Team(1, 0)
        self.team2 = Team(2, 5)

        self.instance = ProblemInstance(
            num_tasks=2,
            num_teams=2,
            tasks={1: self.t1, 2: self.t2},
            teams={1: self.team1, 2: self.team2},
        )

    def test_valid_schedule(self):
        # Task 1 on Team 1 at 0 (ends 10)
        # Task 2 on Team 1 at 10 (ends 30)
        schedule = Schedule(assignments=[Assignment(1, 1, 0), Assignment(2, 1, 10)])
        result = validate_schedule(self.instance, schedule)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

        score = grade_schedule(self.instance, schedule)
        self.assertEqual(score.num_tasks, 2)
        self.assertEqual(score.makespan, 30)
        self.assertEqual(score.total_cost, 20)

    def test_precedence_violation(self):
        # Task 2 starts before Task 1 finishes
        schedule = Schedule(assignments=[Assignment(1, 1, 0), Assignment(2, 1, 5)])
        result = validate_schedule(self.instance, schedule)
        self.assertFalse(result.is_valid)
        # Should have at least one error (precedence or overlap)
        self.assertTrue(any("Precedence violation" in e.message for e in result.errors))

    def test_team_overlap(self):
        # Two tasks on same team overlapping, but no precedence violation
        # Suppose Task 2 didn't depend on Task 1 for this test
        self.t2.predecessors = []
        schedule = Schedule(assignments=[Assignment(1, 1, 0), Assignment(2, 1, 5)])
        result = validate_schedule(self.instance, schedule)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("Team overlap" in e.message for e in result.errors))

    def test_team_availability(self):
        # Team 2 available from 5, Task 1 starts at 0
        schedule = Schedule(assignments=[Assignment(1, 2, 0)])
        result = validate_schedule(self.instance, schedule)
        self.assertFalse(result.is_valid)
        self.assertTrue(
            any("before team 2 is available" in e.message for e in result.errors)
        )

    def test_incompatibility(self):
        # Task 2 not compatible with Team 2
        schedule = Schedule(assignments=[Assignment(2, 2, 20)])
        result = validate_schedule(self.instance, schedule)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("not compatible" in e.message for e in result.errors))

    def test_score_comparison(self):
        s1 = Score(10, 100, 50)
        s2 = Score(10, 100, 60)
        s3 = Score(10, 90, 70)
        s4 = Score(11, 200, 100)

        # Higher tasks is better
        self.assertTrue(s1 < s4)
        # Lower makespan is better
        self.assertTrue(s1 < s3)
        # Lower cost is better
        self.assertTrue(s2 < s1)

        def test_multi_instance_grader(self):
            from paas.grader import MultiInstanceGrader, SimpleNormalizer

            mig = MultiInstanceGrader(normalizer=SimpleNormalizer())

            # Instance 1: 10 tasks total

            inst1 = ProblemInstance(10, 1, {}, {})

            score1 = Score(8, 100, 50)

            # Instance 2: 20 tasks total

            inst2 = ProblemInstance(20, 1, {}, {})

            score2 = Score(10, 150, 80)

            mig.add_result("inst1", score1, inst1)

            mig.add_result("inst2", score2, inst2)

            summary = mig.get_summary()

            self.assertEqual(summary["count"], 2)

            self.assertEqual(summary["total_tasks"], 18)

            # (8/10 + 10/20) / 2 = (0.8 + 0.5) / 2 = 0.65

            self.assertAlmostEqual(summary["avg_completion_rate"], 0.65)

        def test_jury_normalizer(self):
            from paas.grader import MultiInstanceGrader, JuryNormalizer

            mig = MultiInstanceGrader(normalizer=JuryNormalizer())

            inst = ProblemInstance(10, 1, {}, {})

            jury_score = Score(10, 100, 100)

            my_score = Score(10, 80, 120)

            mig.add_result("inst1", my_score, inst, reference=jury_score)

            summary = mig.get_summary()

            self.assertAlmostEqual(summary["avg_relative_tasks"], 1.0)

            self.assertAlmostEqual(summary["avg_relative_makespan"], 0.8)

            self.assertAlmostEqual(summary["avg_relative_cost"], 1.2)
