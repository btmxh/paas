import random
from typing import List, Dict, Optional
from paas.models import ProblemInstance, Schedule, Assignment
from paas.middleware.base import MapResult
from paas.time_budget import TimeBudget


class Ant:
    def __init__(self, num_tasks: int, num_teams: int):
        self.assignments: List[Assignment] = []
        self.team_free_time: Dict[int, int] = {}
        self.task_finish_time: Dict[int, int] = {}

        # Objectives
        self.makespan = 0
        self.total_cost = 0
        self.num_scheduled = 0


class ACOSearchMiddleware(MapResult):
    """
    Ant Colony Optimization (ACO) based search middleware that can start from a seed solution.
    """

    def __init__(
        self,
        alpha: float = 0.5,
        beta: float = 3.0,
        rho: float = 0.1,
        num_ants: int = 40,
        iterations: int = 100,
        q_reward: float = 1000.0,
        seed: int = 8,
        time_factor: float = 1.0,
    ):
        super().__init__(time_factor)
        self.alpha = alpha
        self.beta = beta
        self.rho = rho
        self.num_ants = num_ants
        self.iterations = iterations
        self.q_reward = q_reward
        self.seed = seed

    def _calculate_heuristic(
        self,
        task_id: int,
        team_id: int,
        current_team_time: int,
        task_ready_time: int,
        problem: ProblemInstance,
    ) -> float:
        task = problem.tasks[task_id]
        duration = task.duration
        cost = task.compatible_teams[team_id]
        start_time = max(current_team_time, task_ready_time)
        finish_time = start_time + duration

        h_time = 1.0 / (finish_time + 1.0)
        h_cost = 1.0 / (cost + 1.0)
        return (h_time**1.5) * (h_cost**0.5)

    def map_result(
        self,
        problem: ProblemInstance,
        seed_schedule: Schedule,
        time_limit: float = float("inf"),
    ) -> Schedule:
        random.seed(self.seed)

        with TimeBudget(time_limit) as budget:
            N = problem.num_tasks
            M = problem.num_teams

            successors: Dict[int, List[int]] = {tid: [] for tid in problem.tasks}
            indegree_base: Dict[int, int] = {tid: 0 for tid in problem.tasks}
            for tid, task in problem.tasks.items():
                indegree_base[tid] = len(task.predecessors)
                for p in task.predecessors:
                    successors[p].append(tid)

            pheromones: Dict[int, Dict[int, float]] = {}
            for tid, task in problem.tasks.items():
                pheromones[tid] = {}
                for team_id in task.compatible_teams:
                    pheromones[tid][team_id] = 1.0

            # Use seed solution to boost initial pheromones
            if seed_schedule.assignments:
                # Calculate seed makespan for reward
                seed_makespan = 0
                for a in seed_schedule.assignments:
                    duration = problem.tasks[a.task_id].duration
                    seed_makespan = max(seed_makespan, a.start_time + duration)

                initial_boost = self.q_reward / (seed_makespan + 1.0)
                for a in seed_schedule.assignments:
                    if a.task_id in pheromones and a.team_id in pheromones[a.task_id]:
                        pheromones[a.task_id][a.team_id] += initial_boost

            best_global_ant: Optional[Ant] = None

            # If seed exists, it's our first global best
            if seed_schedule.assignments:
                best_global_ant = Ant(N, M)
                best_global_ant.assignments = seed_schedule.assignments
                best_global_ant.num_scheduled = len(seed_schedule.assignments)

                total_cost = 0
                makespan = 0
                for a in seed_schedule.assignments:
                    dur = problem.tasks[a.task_id].duration
                    total_cost += problem.tasks[a.task_id].compatible_teams[a.team_id]
                    makespan = max(makespan, a.start_time + dur)
                best_global_ant.total_cost = total_cost
                best_global_ant.makespan = makespan

            for it in range(self.iterations):
                if budget.is_expired():
                    break

                ants: List[Ant] = []
                for _ in range(self.num_ants):
                    ant = Ant(N, M)
                    for tid, team in problem.teams.items():
                        ant.team_free_time[tid] = team.available_from

                    current_indegree = indegree_base.copy()
                    available_tasks = [
                        tid for tid, deg in current_indegree.items() if deg == 0
                    ]

                    while available_tasks:
                        candidates = []
                        for task_id in available_tasks:
                            ready_time = 0
                            task = problem.tasks[task_id]
                            for pred in task.predecessors:
                                ready_time = max(
                                    ready_time, ant.task_finish_time.get(pred, 0)
                                )

                            if task_id in pheromones:
                                for team_id in pheromones[task_id]:
                                    tau = pheromones[task_id][team_id]
                                    eta = self._calculate_heuristic(
                                        task_id,
                                        team_id,
                                        ant.team_free_time[team_id],
                                        ready_time,
                                        problem,
                                    )
                                    prob = (tau**self.alpha) * (eta**self.beta)
                                    candidates.append(
                                        {
                                            "task_id": task_id,
                                            "team_id": team_id,
                                            "prob": prob,
                                            "ready": ready_time,
                                        }
                                    )

                        if not candidates:
                            break

                        total_prob = sum(c["prob"] for c in candidates)
                        if total_prob == 0:
                            chosen = random.choice(candidates)
                        else:
                            r = random.uniform(0, total_prob)
                            cumsum = 0
                            chosen = candidates[-1]
                            for c in candidates:
                                cumsum += c["prob"]
                                if r <= cumsum:
                                    chosen = c
                                    break

                        task_id, team_id, r_time = (
                            chosen["task_id"],
                            chosen["team_id"],
                            chosen["ready"],
                        )
                        start = max(ant.team_free_time[team_id], r_time)
                        finish = start + problem.tasks[task_id].duration
                        cost = problem.tasks[task_id].compatible_teams[team_id]

                        ant.assignments.append(Assignment(task_id, team_id, start))
                        ant.team_free_time[team_id] = finish
                        ant.task_finish_time[task_id] = finish
                        ant.total_cost += cost
                        ant.makespan = max(ant.makespan, finish)

                        available_tasks.remove(task_id)
                        for succ in successors[task_id]:
                            current_indegree[succ] -= 1
                            if current_indegree[succ] == 0:
                                available_tasks.append(succ)

                    ant.num_scheduled = len(ant.assignments)
                    ants.append(ant)

                if not ants:
                    continue

                ants.sort(key=lambda x: (-x.num_scheduled, x.makespan, x.total_cost))
                iter_best = ants[0]

                if best_global_ant is None:
                    best_global_ant = iter_best
                else:
                    if iter_best.num_scheduled > best_global_ant.num_scheduled:
                        best_global_ant = iter_best
                    elif iter_best.num_scheduled == best_global_ant.num_scheduled:
                        if iter_best.makespan < best_global_ant.makespan:
                            best_global_ant = iter_best
                        elif iter_best.makespan == best_global_ant.makespan:
                            if iter_best.total_cost < best_global_ant.total_cost:
                                best_global_ant = iter_best

                for tid in pheromones:
                    for team_id in pheromones[tid]:
                        pheromones[tid][team_id] *= 1.0 - self.rho

                if best_global_ant and best_global_ant.num_scheduled > 0:
                    reward = self.q_reward / (best_global_ant.makespan + 1.0)
                    for assignment in best_global_ant.assignments:
                        if (
                            assignment.task_id in pheromones
                            and assignment.team_id in pheromones[assignment.task_id]
                        ):
                            pheromones[assignment.task_id][assignment.team_id] += reward

            if best_global_ant:
                return Schedule(assignments=best_global_ant.assignments)
            return seed_schedule
