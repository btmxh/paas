from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from .models import ProblemInstance, Schedule


@dataclass
class Score:
    num_tasks: int
    makespan: int
    total_cost: int

    def __lt__(self, other: "Score") -> bool:
        # Prioritize:
        # 1. Maximize num_tasks
        if self.num_tasks != other.num_tasks:
            return self.num_tasks < other.num_tasks
        # 2. Minimize makespan
        if self.makespan != other.makespan:
            return self.makespan > other.makespan
        # 3. Minimize total_cost
        return self.total_cost > other.total_cost

    def to_dict(self):
        return {
            "num_tasks": self.num_tasks,
            "makespan": self.makespan,
            "total_cost": self.total_cost,
        }


def grade_schedule(instance: ProblemInstance, schedule: Schedule) -> Score:
    if not schedule.assignments:
        return Score(num_tasks=0, makespan=0, total_cost=0)

    num_tasks = len(schedule.assignments)
    makespan = 0
    total_cost = 0

    for assignment in schedule.assignments:
        task = instance.tasks[assignment.task_id]

        # Calculate completion time
        finish_time = assignment.start_time + task.duration
        if finish_time > makespan:
            makespan = finish_time

        # Calculate cost
        cost = task.compatible_teams.get(assignment.team_id, 0)
        total_cost += cost

    return Score(num_tasks=num_tasks, makespan=makespan, total_cost=total_cost)


class Normalizer(ABC):
    @abstractmethod
    def normalize(
        self, score: Score, instance: ProblemInstance, reference: Optional[Score] = None
    ) -> Dict[str, float]:
        pass


class SimpleNormalizer(Normalizer):
    """
    Normalizes based on instance size (num_tasks).
    """

    def normalize(
        self, score: Score, instance: ProblemInstance, reference: Optional[Score] = None
    ) -> Dict[str, float]:
        return {
            "completion_rate": (
                score.num_tasks / instance.num_tasks if instance.num_tasks > 0 else 0
            )
        }


class JuryNormalizer(Normalizer):
    """
    Normalizes based on a reference jury score.
    Metrics are relative to jury (e.g., 1.0 means same as jury, < 1.0 means better for minimizations).
    """

    def normalize(
        self, score: Score, instance: ProblemInstance, reference: Optional[Score] = None
    ) -> Dict[str, float]:
        if not reference:
            return {}

        result = {}
        if reference.num_tasks > 0:
            result["relative_tasks"] = score.num_tasks / reference.num_tasks
        if reference.makespan > 0:
            result["relative_makespan"] = score.makespan / reference.makespan
        if reference.total_cost > 0:
            result["relative_cost"] = score.total_cost / reference.total_cost

        return result


class MultiInstanceGrader:
    """
    Utility for aggregating and normalizing scores across multiple instances.
    """

    def __init__(self, normalizer: Optional[Normalizer] = None):
        self.results: List[Dict[str, Any]] = []
        self.normalizer = normalizer or SimpleNormalizer()

    def add_result(
        self,
        instance_id: str,
        score: Score,
        instance: ProblemInstance,
        reference: Optional[Score] = None,
    ):
        data = {
            "instance_id": instance_id,
            "score": score,
            "instance_size": instance.num_tasks,
        }

        normalization = self.normalizer.normalize(score, instance, reference)
        data.update(normalization)

        self.results.append(data)

    def get_summary(self) -> Dict[str, Any]:
        if not self.results:
            return {}

        total_tasks = sum(r["score"].num_tasks for r in self.results)
        total_makespan = sum(r["score"].makespan for r in self.results)
        total_cost = sum(r["score"].total_cost for r in self.results)
        n = len(self.results)

        summary = {
            "count": n,
            "total_tasks": total_tasks,
            "total_makespan": total_makespan,
            "total_cost": total_cost,
            "avg_tasks": total_tasks / n,
            "avg_makespan": total_makespan / n,
            "avg_cost": total_cost / n,
        }

        # Average any numeric normalization metrics
        metrics = set()
        for r in self.results:
            for k, v in r.items():
                if isinstance(v, (int, float)) and k not in [
                    "instance_size",
                    "score",
                ]:
                    metrics.add(k)

        for metric in metrics:
            values = [r[metric] for r in self.results if metric in r]
            if values:
                summary[f"avg_{metric}"] = sum(values) / len(values)

        return summary
