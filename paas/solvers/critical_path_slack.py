from paas.models import ProblemInstance, Schedule, Assignment
from paas.middleware.base import Runnable


class CriticalPathSlackSolver(Runnable):
    """
    Optimized Scheduler:
    1. Critical Path (Time)
    2. Slack-Aware Cost (Cost)
    3. Versatility/Scarcity (Tie-Breaker for resource management)
    """

    def run(self, problem: ProblemInstance) -> Schedule:
        tasks = problem.tasks
        teams = problem.teams

        # --- 1. Pre-calculation ---

        # A. Critical Path Priority
        successors = {tid: [] for tid in tasks}
        for tid, task in tasks.items():
            for pred in task.predecessors:
                successors[pred].append(tid)

        memo_priority = {}

        def compute_priority(tid):
            if tid in memo_priority:
                return memo_priority[tid]
            max_succ_priority = 0
            if successors[tid]:
                max_succ_priority = max(compute_priority(s) for s in successors[tid])
            res = tasks[tid].duration + max_succ_priority
            memo_priority[tid] = res
            return res

        for tid in tasks:
            compute_priority(tid)

        project_makespan_lb = max(memo_priority.values()) if memo_priority else 0

        # B. Team Versatility (The Fix)
        # Count how many tasks can use each team.
        # We prefer using teams with LOW counts (Specialists) over HIGH counts (Generalists).
        team_versatility = {t_id: 0 for t_id in teams}
        for task in tasks.values():
            for t_id in task.compatible_teams:
                team_versatility[t_id] += 1

        # --- 2. Main Loop ---
        team_available_time = {
            t_id: team.available_from for t_id, team in teams.items()
        }
        task_completion_time = {}
        scheduled_task_ids = set()
        assignments = []

        ready_tasks = set(tid for tid, t in tasks.items() if not t.predecessors)
        unscheduled_dependency_counts = {
            tid: len(t.predecessors) for tid, t in tasks.items()
        }

        while len(scheduled_task_ids) < len(tasks):
            if not ready_tasks:
                break

            # Step A: Critical Path Selection
            best_task_id = max(
                ready_tasks,
                key=lambda tid: (
                    memo_priority[tid],
                    tasks[tid].duration,
                    -len(tasks[tid].compatible_teams),
                ),
            )

            task = tasks[best_task_id]
            task_priority = memo_priority[best_task_id]

            min_start_from_preds = max(
                (task_completion_time[p] for p in task.predecessors), default=0
            )

            # Step B: Team Selection with Versatility Tie-Breaker
            safe_candidates = []
            unsafe_candidates = []

            for team_id, cost in task.compatible_teams.items():
                start = max(team_available_time[team_id], min_start_from_preds)
                chain_finish = start + task_priority

                # Fetch how "valuable" this team is to others
                versatility = team_versatility[team_id]

                if chain_finish <= project_makespan_lb:
                    # SAFE: (Cost, Start, Versatility, TeamID)
                    # We add 'versatility' as the 3rd key.
                    # If Cost and Start are identical, we pick the LOWER versatility (Team 3 over Team 2)
                    safe_candidates.append((cost, start, versatility, team_id))
                else:
                    # UNSAFE: (Start, Cost, Versatility, TeamID)
                    unsafe_candidates.append((start, cost, versatility, team_id))

            selected_start = -1
            selected_team = None

            if safe_candidates:
                # We sort by:
                # 1. Min Cost
                # 2. Min Start Time
                # 3. Min Versatility (The tie-breaker!)
                safe_candidates.sort()
                _, selected_start, _, selected_team = safe_candidates[0]
            elif unsafe_candidates:
                unsafe_candidates.sort()
                selected_start, _, _, selected_team = unsafe_candidates[0]
            else:
                ready_tasks.remove(best_task_id)
                continue

            # --- Update global states ---
            finish = selected_start + task.duration
            team_available_time[selected_team] = finish
            task_completion_time[best_task_id] = finish
            scheduled_task_ids.add(best_task_id)
            assignments.append(Assignment(best_task_id, selected_team, selected_start))

            if selected_start + task_priority > project_makespan_lb:
                project_makespan_lb = selected_start + task_priority

            ready_tasks.remove(best_task_id)
            for succ_id in successors[best_task_id]:
                unscheduled_dependency_counts[succ_id] -= 1
                if unscheduled_dependency_counts[succ_id] == 0:
                    ready_tasks.add(succ_id)

        return Schedule(assignments)
