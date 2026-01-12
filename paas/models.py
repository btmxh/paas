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


@dataclass
class Assignment:
    task_id: int
    team_id: int
    start_time: int


@dataclass
class Schedule:
    assignments: List[Assignment]
