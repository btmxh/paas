import unittest
from unittest.mock import MagicMock, patch
from paas.dataset import Instance
from paas.hustack_main import run_single_experiment
from paas.models import ProblemInstance, Schedule, Assignment
from paas.grader import Score


class TestExperiment(unittest.TestCase):
    def test_run_single_experiment_success(self):
        # Mock instance
        mock_problem = MagicMock(spec=ProblemInstance)
        mock_instance = Instance(id="test_01", problem=mock_problem)

        # Mock solver class
        mock_solver_cls = MagicMock()
        mock_solver_cls.__name__ = "MockSolver"

        # We need to patch Pipeline because run_single_experiment instantiates it
        with patch("paas.main.Pipeline") as MockPipeline:
            mock_pipeline_instance = MockPipeline.return_value
            mock_pipeline_instance.run.return_value = Schedule(
                assignments=[Assignment(task_id=1, team_id=1, start_time=0)]
            )

            # Patch grade_schedule to return a dummy score
            with patch("paas.main.grade_schedule") as mock_grade:
                mock_grade.return_value = Score(num_tasks=1, makespan=10, total_cost=5)

                result = run_single_experiment(
                    mock_instance, mock_solver_cls, time_limit=1
                )

                self.assertEqual(result["status"], "success")
                self.assertEqual(result["instance"], "test_01")
                self.assertEqual(result["solver"], "MockSolver")
                self.assertEqual(result["score"]["total_cost"], 5)

    def test_run_single_experiment_failure(self):
        # Mock instance
        mock_problem = MagicMock(spec=ProblemInstance)
        mock_instance = Instance(id="test_02", problem=mock_problem)

        # Mock solver class
        mock_solver_cls = MagicMock()
        mock_solver_cls.__name__ = "BrokenSolver"

        with patch("paas.main.Pipeline") as MockPipeline:
            mock_pipeline_instance = MockPipeline.return_value
            mock_pipeline_instance.run.side_effect = Exception("Boom")

            result = run_single_experiment(mock_instance, mock_solver_cls, time_limit=1)

            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["error"], "Boom")


if __name__ == "__main__":
    unittest.main()
