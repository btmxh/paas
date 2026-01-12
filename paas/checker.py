from dataclasses import dataclass, field
from typing import List, Optional
from .models import ProblemInstance, Schedule, Assignment


@dataclass
class ValidationError:
    message: str
    assignment: Optional[Assignment] = None


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)


def validate_schedule(
    instance: ProblemInstance, schedule: Schedule
) -> ValidationResult:
    errors = []
    scheduled_tasks = {}  # task_id -> assignment
    team_schedules = {}  # team_id -> list of assignments

    for assignment in schedule.assignments:
        # Check task existence
        if assignment.task_id not in instance.tasks:
            errors.append(
                ValidationError(f"Task {assignment.task_id} does not exist", assignment)
            )
            continue

        # Check team existence
        if assignment.team_id not in instance.teams:
            errors.append(
                ValidationError(f"Team {assignment.team_id} does not exist", assignment)
            )
            continue

        task = instance.tasks[assignment.task_id]
        team = instance.teams[assignment.team_id]

        # Check task uniqueness
        if assignment.task_id in scheduled_tasks:
            errors.append(
                ValidationError(
                    f"Task {assignment.task_id} is scheduled multiple times", assignment
                )
            )
        else:
            scheduled_tasks[assignment.task_id] = assignment

        # Check compatibility
        if assignment.team_id not in task.compatible_teams:
            errors.append(
                ValidationError(
                    f"Team {assignment.team_id} is not compatible with Task {assignment.task_id}",
                    assignment,
                )
            )

        # Check team availability
        if assignment.start_time < team.available_from:
            errors.append(
                ValidationError(
                    f"Task {assignment.task_id} starts at {assignment.start_time}, before team {assignment.team_id} is available at {team.available_from}",
                    assignment,
                )
            )

        # Group by team for overlap check
        if assignment.team_id not in team_schedules:
            team_schedules[assignment.team_id] = []
        team_schedules[assignment.team_id].append(assignment)

    # Check precedence constraints
    for task_id, assignment in scheduled_tasks.items():
        task = instance.tasks[task_id]
        for pred_id in task.predecessors:
            if pred_id in scheduled_tasks:
                pred_assignment = scheduled_tasks[pred_id]
                pred_task = instance.tasks[pred_id]
                if (
                    assignment.start_time
                    < pred_assignment.start_time + pred_task.duration
                ):
                    errors.append(
                        ValidationError(
                            f"Precedence violation: Task {task_id} starts at {assignment.start_time} "
                            f"before predecessor Task {pred_id} finishes at {pred_assignment.start_time + pred_task.duration}",
                            assignment,
                        )
                    )

    # Check team overlaps
    for team_id, assignments in team_schedules.items():
        # Sort assignments by start time
        sorted_assignments = sorted(assignments, key=lambda x: x.start_time)
        for i in range(len(sorted_assignments) - 1):
            curr = sorted_assignments[i]
            next_a = sorted_assignments[i + 1]
            curr_task = instance.tasks[curr.task_id]
            if curr.start_time + curr_task.duration > next_a.start_time:
                errors.append(
                    ValidationError(
                        f"Team overlap: Team {team_id} is busy with Task {curr.task_id} "
                        f"until {curr.start_time + curr_task.duration}, but Task {next_a.task_id} "
                        f"starts at {next_a.start_time}",
                        next_a,
                    )
                )

    return ValidationResult(is_valid=len(errors) == 0, errors=errors)
