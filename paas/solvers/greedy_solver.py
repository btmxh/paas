from ..models import ProblemInstance, Schedule, Assignment
import heapq
import time


class GreedySolver:
    """
    A greedy solver that schedules tasks based on Shortest Processing Time (SPT)
    and assigns them to teams based on Earliest Start Time (EST) and then lowest cost.
    """

    def solve(self, instance: ProblemInstance, time_limit: float = 60.0) -> Schedule:
        start_time = time.time()

        # Track team availability (team_id -> available_time)
        # Initially, it's the team's 'available_from' time.
        team_availability = {
            t_id: t.available_from for t_id, t in instance.teams.items()
        }

        # Track task completion times to handle dependencies
        task_completion_times = {}

        # Track in-degree (number of unsatisfied predecessors) for each task
        # We need a mutable copy since we decrement it.
        in_degree = {t_id: len(t.predecessors) for t_id, t in instance.tasks.items()}

        # Priority Queue for available tasks (in_degree == 0)
        # Priority: (duration, task_id).
        # Shorter tasks are processed first (SPT heuristic).
        priority_queue = []
        for t_id, task in instance.tasks.items():
            if in_degree[t_id] == 0:
                heapq.heappush(priority_queue, (task.duration, t_id))

        assignments = []

        while priority_queue:
            if time.time() - start_time > time_limit:
                break

            # Improvement: Removed random.shuffle to maintain the heap property and strict greedy behavior.
            # If randomness is desired, a different strategy (e.g., picking from top-k) should be used.

            # Pop the task with the shortest duration
            duration, task_id = heapq.heappop(priority_queue)
            task = instance.tasks[task_id]

            best_team_id = -1
            best_start_time = float("inf")
            best_cost = float("inf")

            # Iterate only over compatible teams
            for team_id, cost in task.compatible_teams.items():
                if team_id not in instance.teams:
                    continue  # Should not happen if data is consistent

                # Calculate earliest start time for this task on this team
                # It's max(team's availability, max(predecessors' completion times))

                max_pred_completion = 0
                if task.predecessors:
                    # Check if all predecessors are completed (they should be if in_degree is 0 and we popped it)
                    # We take the max of their completion times.
                    # Note: If a predecessor wasn't scheduled (e.g., due to time limit), this would crash or be incomplete.
                    # With the current flow, we only process tasks whose predecessors are processed.
                    max_pred_completion = max(
                        task_completion_times.get(p_id, 0) for p_id in task.predecessors
                    )

                current_team_availability = team_availability[team_id]
                possible_start_time = max(
                    max_pred_completion, current_team_availability
                )

                # Greedy choice: Earliest Start Time, then Lowest Cost
                if possible_start_time < best_start_time or (
                    possible_start_time == best_start_time and cost < best_cost
                ):
                    best_team_id = team_id
                    best_start_time = possible_start_time
                    best_cost = cost

            if best_team_id != -1:
                # Assign task
                new_completion_time = best_start_time + duration
                team_availability[best_team_id] = new_completion_time
                task_completion_times[task_id] = new_completion_time

                assignments.append(
                    Assignment(
                        task_id=task_id,
                        team_id=best_team_id,
                        start_time=int(best_start_time),
                    )
                )

                # Update neighbors (successors)
                for successor_id in task.successors:
                    in_degree[successor_id] -= 1
                    if in_degree[successor_id] == 0:
                        successor_task = instance.tasks[successor_id]
                        heapq.heappush(
                            priority_queue, (successor_task.duration, successor_id)
                        )
            else:
                # Task could not be assigned to any compatible team (e.g. if compatible_teams is empty)
                # In this strict dependency graph, this might block all successors.
                pass

        return Schedule(assignments=assignments)
