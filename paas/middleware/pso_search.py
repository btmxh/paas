import random
import math
from typing import List, Optional
from paas.models import ProblemInstance, Schedule, Assignment
from paas.middleware.base import MapResult
from paas.time_budget import TimeBudget


class ScheduleResult:
    def __init__(self):
        self.assignments: List[Assignment] = []
        self.makespan = 0
        self.total_cost = 0
        self.scheduled_count = 0


class Particle:
    def __init__(self, size: int):
        self.position = [random.random() for _ in range(size)]
        self.velocity = [0.0 for _ in range(size)]

        self.best_position = list(self.position)
        self.best_fitness = float("inf")
        self.best_result: Optional[ScheduleResult] = None


class PSOSearchMiddleware(MapResult):
    """


    Particle Swarm Optimization (PSO) based search middleware that can start from a seed solution.


    """

    def __init__(
        self,
        swarm_size: int = 100,
        max_iterations: int = 200,
        w: float = 0.4,
        c1: float = 1.5,
        c2: float = 2.0,
        seed: int = 8,
        time_factor: float = 1.0,
    ):
        super().__init__(time_factor)

        self.swarm_size = swarm_size

        self.max_iterations = max_iterations

        self.w = w

        self.c1 = c1

        self.c2 = c2

        self.seed = seed

    def _decode_particle(
        self, position: List[float], problem: ProblemInstance
    ) -> ScheduleResult:
        N = problem.num_tasks

        priorities = position[:N]

        team_selectors = position[N:]

        current_team_times = {
            tid: team.available_from for tid, team in problem.teams.items()
        }

        current_in_degree = {
            tid: len(task.predecessors) for tid, task in problem.tasks.items()
        }

        valid_start_time_preds = {tid: 0 for tid in problem.tasks}

        result = ScheduleResult()

        ready_tasks = [tid for tid, deg in current_in_degree.items() if deg == 0]

        while ready_tasks:
            selected_task_id = max(ready_tasks, key=lambda tid: priorities[tid - 1])

            ready_tasks.remove(selected_task_id)

            task = problem.tasks[selected_task_id]

            options = list(task.compatible_teams.items())

            if not options:
                continue

            selector_value = team_selectors[selected_task_id - 1]

            if selector_value >= 1.0:
                selector_value = 0.99999

            num_options = len(options)

            choice_index = int(math.floor(selector_value * num_options))

            assigned_team_id, task_cost = options[choice_index]

            start_lim_preds = valid_start_time_preds[selected_task_id]

            start_lim_team = current_team_times[assigned_team_id]

            actual_start_time = max(start_lim_preds, start_lim_team)

            actual_finish_time = actual_start_time + task.duration

            current_team_times[assigned_team_id] = actual_finish_time

            result.assignments.append(
                Assignment(selected_task_id, assigned_team_id, actual_start_time)
            )

            result.total_cost += task_cost

            result.makespan = max(result.makespan, actual_finish_time)

            result.scheduled_count += 1

            for neighbor_id in task.successors:
                current_in_degree[neighbor_id] -= 1

                valid_start_time_preds[neighbor_id] = max(
                    valid_start_time_preds[neighbor_id], actual_finish_time
                )

                if current_in_degree[neighbor_id] == 0:
                    ready_tasks.append(neighbor_id)

        return result

    def _calculate_fitness(
        self, result: ScheduleResult, problem: ProblemInstance
    ) -> float:
        W1 = 10000000

        W2 = 1000

        W3 = 1

        penalty_unscheduled = (problem.num_tasks - result.scheduled_count) * W1

        score_time = result.makespan * W2

        score_cost = result.total_cost * W3

        return penalty_unscheduled + score_time + score_cost

    def _encode_schedule(
        self, schedule: Schedule, problem: ProblemInstance
    ) -> List[float]:
        """


        Attempts to encode a schedule into a particle position.


        """

        N = problem.num_tasks

        position = [0.5] * (2 * N)

        # Priorities based on start time (earlier start = higher priority)

        # We want priorities[tid-1] to be large for small start_times

        max_start = 0

        assignments_map = {}

        for a in schedule.assignments:
            assignments_map[a.task_id] = a

            max_start = max(max_start, a.start_time)

        for tid in range(1, N + 1):
            if tid in assignments_map:
                a = assignments_map[tid]

                # Map [0, max_start] to [1.0, 0.0]

                if max_start > 0:
                    position[tid - 1] = 1.0 - (a.start_time / max_start)

                else:
                    position[tid - 1] = 1.0

                # Team selector

                task = problem.tasks[tid]

                options = list(task.compatible_teams.items())

                for idx, (team_id, _) in enumerate(options):
                    if team_id == a.team_id:
                        # Map index to range [idx/len, (idx+1)/len]

                        position[N + tid - 1] = (idx + 0.5) / len(options)

                        break

            else:
                position[tid - 1] = 0.0  # Low priority if not scheduled

        return position

    def map_result(
        self,
        problem: ProblemInstance,
        result: Schedule,
        time_limit: float = float("inf"),
    ) -> Schedule:
        random.seed(self.seed)

        with TimeBudget(time_limit) as budget:
            dim = 2 * problem.num_tasks
            swarm = [Particle(dim) for _ in range(self.swarm_size)]

            # Inject seed into first particle
            if result.assignments:
                seed_pos = self._encode_schedule(result, problem)
                swarm[0].position = seed_pos
                swarm[0].best_position = list(seed_pos)

            global_best_fitness = float("inf")
            global_best_result: Optional[ScheduleResult] = None
            global_best_position: Optional[List[float]] = None

            for iteration in range(self.max_iterations):
                if budget.is_expired():
                    break

                for particle in swarm:
                    decode_result = self._decode_particle(particle.position, problem)
                    fitness = self._calculate_fitness(decode_result, problem)

                    if fitness < particle.best_fitness:
                        particle.best_fitness = fitness
                        particle.best_position = list(particle.position)
                        particle.best_result = decode_result

                    if fitness < global_best_fitness:
                        global_best_fitness = fitness
                        global_best_position = list(particle.position)
                        global_best_result = decode_result

                if global_best_position is None:
                    continue

                for particle in swarm:
                    for i in range(dim):
                        r1 = random.random()
                        r2 = random.random()

                        vel_cognitive = (
                            self.c1
                            * r1
                            * (particle.best_position[i] - particle.position[i])
                        )
                        vel_social = (
                            self.c2
                            * r2
                            * (global_best_position[i] - particle.position[i])
                        )

                        particle.velocity[i] = (
                            (self.w * particle.velocity[i]) + vel_cognitive + vel_social
                        )
                        particle.position[i] += particle.velocity[i]

                        if particle.position[i] < 0.0:
                            particle.position[i] = 0.0
                            particle.velocity[i] *= -0.5
                        elif particle.position[i] > 1.0:
                            particle.position[i] = 1.0
                            particle.velocity[i] *= -0.5

            if global_best_result:
                # If seed was better, it might still win via global_best if decode is exact or close
                return Schedule(assignments=global_best_result.assignments)
            return result
