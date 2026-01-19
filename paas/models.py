from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class Task:
    id: int
    duration: int
    predecessors: List[int] = field(default_factory=list)
    successors: List[int] = field(default_factory=list)
    # Map of compatible team_id -> cost
    compatible_teams: Dict[int, int] = field(default_factory=dict)


@dataclass
class Team:
    id: int
    available_from: int


@dataclass
class ProblemInstance:
    num_tasks: int
    num_teams: int
    tasks: Dict[int, Task]
    teams: Dict[int, Team]

    def assert_continuous_indices(self):
        expected_task_ids = set(range(self.num_tasks))
        actual_task_ids = set(self.tasks.keys())
        if expected_task_ids != actual_task_ids:
            raise ValueError(
                f"Task IDs are not continuous. Expected {expected_task_ids}, got {actual_task_ids}"
            )

        expected_team_ids = set(range(self.num_teams))
        actual_team_ids = set(self.teams.keys())
        if expected_team_ids != actual_team_ids:
            raise ValueError(
                f"Team IDs are not continuous. Expected {expected_team_ids}, got {actual_team_ids}"
            )


@dataclass
class Assignment:
    task_id: int
    team_id: int
    start_time: int


@dataclass
class Schedule:
    assignments: List[Assignment]

    def print(self):
        print(len(self.assignments))
        for assignment in self.assignments:
            print(f"{assignment.task_id} {assignment.team_id} {assignment.start_time}")
