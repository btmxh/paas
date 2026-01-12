from dataclasses import dataclass, field


@dataclass
class Task:
    id: int
    duration: int
    predecessors: list[int] = field(default_factory=list)
    successors: list[int] = field(default_factory=list)
    # Map of compatible team_id -> cost
    compatible_teams: dict[int, int] = field(default_factory=dict)


@dataclass
class Team:
    id: int
    available_from: int


@dataclass
class ProblemInstance:
    num_tasks: int
    num_teams: int
    tasks: dict[int, Task]
    teams: dict[int, Team]


@dataclass
class Assignment:
    task_id: int
    team_id: int
    start_time: int


@dataclass
class Schedule:
    assignments: list[Assignment]
