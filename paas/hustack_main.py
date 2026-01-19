from sys import stderr, stdout
from paas.middleware import ContinuousIndexer
from paas.solvers import CPSolver
import json
import time
import concurrent.futures
from typing import Dict, Any, Callable

from paas.dataset import Dataset, Instance
from paas.grader import grade_schedule, JuryNormalizer

from paas.middleware.base import Pipeline
from paas.middleware.cycle_remover import CycleRemover
from paas.middleware.impossible_task_remover import ImpossibleTaskRemover
from paas.middleware.dependency_pruner import DependencyPruner


def run_single_experiment(
    instance: Instance, pipeline_fn: Callable[[], Pipeline], time_limit: float
) -> Dict[str, Any]:
    pipeline = pipeline_fn()

    start_time = time.time()
    try:
        schedule = pipeline.run(instance.problem, time_limit=time_limit)
        elapsed = time.time() - start_time

        score = grade_schedule(instance.problem, schedule)

        jury_score = None
        if instance.sample_solution_result:
            jury_score = grade_schedule(
                instance.problem, instance.sample_solution_result
            )

        normalizer = JuryNormalizer()
        normalized_scores = normalizer.normalize(score, instance.problem, jury_score)

        return {
            "instance": instance.id,
            "status": "success",
            "time_elapsed": elapsed,
            "score": score.to_dict(),
            "normalized": normalized_scores,
            "assignments_count": len(schedule.assignments),
        }

    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "instance": instance.id,
            "status": "failed",
            "error": str(e),
            "time_elapsed": elapsed,
        }


def new_pipeline() -> Pipeline:
    return Pipeline(
        middlewares=[
            ImpossibleTaskRemover(),
            CycleRemover(),
            DependencyPruner(),
            ContinuousIndexer(),
        ],
        solver=CPSolver(),
    )


def main():
    dataset = Dataset.hustack()
    results = []

    time_limit = float("inf")  # seconds

    print(f"Running experiments on {len(dataset.instances)} instances.", file=stderr)
    print(f"Time limit per run: {time_limit}s", file=stderr)

    # Use ProcessPoolExecutor for true parallelism
    # Note: If memory usage is too high, reduce max_workers
    with concurrent.futures.ProcessPoolExecutor() as executor:
        future_to_task = {
            executor.submit(
                run_single_experiment, instance, new_pipeline, time_limit
            ): instance.id
            for instance in dataset.instances
        }

        for future in concurrent.futures.as_completed(future_to_task):
            inst_id = future_to_task[future]
            try:
                data = future.result()
                results.append(data)
                status = data["status"]
                if status == "success":
                    score_str = f"Tasks: {data['assignments_count']}, Cost: {data['score']['total_cost']}"
                    # Add normalized score if available
                    if "relative_makespan" in data["normalized"]:
                        score_str += f", RelMakespan: {data['normalized']['relative_makespan']:.2f}"
                    if "relative_cost" in data["normalized"]:
                        score_str += (
                            f", RelCost: {data['normalized']['relative_cost']:.2f}"
                        )
                    print(f"[{inst_id}]: Success ({score_str})", file=stderr)
                else:
                    print(f"[{inst_id}]: Failed ({data.get('error')})", file=stderr)
            except Exception as exc:
                print(f"[{inst_id}] generated an exception: {exc}", file=stderr)

    results.sort(key=lambda x: x["instance"])
    # Dump results
    # output_file = "results.json"
    # with open(output_file, "w") as f:
    json.dump(results, stdout, indent=2)

    print("Results saved to stdout", file=stderr)


if __name__ == "__main__":
    main()
