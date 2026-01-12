from dataclasses import dataclass
from typing import Optional
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


class MultiInstanceGrader:
    """
    Utility for aggregating and normalizing scores across multiple instances.
    """

    def __init__(self):
        self.results = []

    def add_result(
        self, instance_id: str, score: Score, instance: Optional[ProblemInstance] = None
    ):
        data = {
            "instance_id": instance_id,
            "score": score,
        }
        if instance:
            data["instance_size"] = instance.num_tasks
            # Normalized values (0 to 1 range, where 1 is usually "better" for tasks,
            # but for makespan/cost lower is better, so normalization might be tricky without bounds)
            data["completion_rate"] = (
                score.num_tasks / instance.num_tasks if instance.num_tasks > 0 else 0
            )

        self.results.append(data)

    def get_summary(self):
        if not self.results:
            return {}

        total_tasks = sum(r["score"].num_tasks for r in self.results)
        total_makespan = sum(r["score"].makespan for r in self.results)
        total_cost = sum(r["score"].total_cost for r in self.results)

        summary = {
            "count": len(self.results),
            "total_tasks": total_tasks,
            "total_makespan": total_makespan,
            "total_cost": total_cost,
            "avg_tasks": total_tasks / len(self.results),
            "avg_makespan": total_makespan / len(self.results),
            "avg_cost": total_cost / len(self.results),
        }

        if all("completion_rate" in r for r in self.results):
            summary["avg_completion_rate"] = sum(
                r["completion_rate"] for r in self.results
            ) / len(self.results)

        return summary
