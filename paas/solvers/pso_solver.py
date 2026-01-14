import random
import time
import math
from typing import List, Optional
from paas.models import ProblemInstance, Schedule, Assignment
from paas.middleware.base import Solver


class ScheduleResult:
    def __init__(self):
        self.assignments: List[Assignment] = []
        self.makespan = 0
        self.total_cost = 0
        self.scheduled_count = 0


class Particle:
    def __init__(self, size: int):
        # Position: [Priorities (N) ... | TeamSelectors (N) ...]
        self.position = [random.random() for _ in range(size)]
        self.velocity = [0.0 for _ in range(size)]

        self.best_position = list(self.position)
        self.best_fitness = float("inf")
        self.best_result: Optional[ScheduleResult] = None


class PSOSolver(Solver):
    """
    Particle Swarm Optimization (PSO) based solver for the Project Assignment and Scheduling (PaaS) problem.
    """

    def __init__(
        self,
        swarm_size: int = 100,
        max_iterations: int = 200,
        w: float = 0.4,
        c1: float = 1.5,
        c2: float = 2.0,
        time_limit: float = 10.0,
        seed: int = 8,
        time_factor: float = 1.0,
    ):
        super().__init__(time_factor)
        self.swarm_size = swarm_size
        self.max_iterations = max_iterations
        self.w = w
        self.c1 = c1
        self.c2 = c2
        self.time_limit = time_limit
        self.seed = seed

    def _decode_particle(
        self, position: List[float], problem: ProblemInstance
    ) -> ScheduleResult:
        """
        Converts a continuous particle vector into a valid schedule using Serial SGS.
        """
        N = problem.num_tasks
        priorities = position[:N]  # Determines order
        team_selectors = position[N:]  # Determines WHO does it

        # Simulation state
        current_team_times = {
            tid: team.available_from for tid, team in problem.teams.items()
        }
        current_in_degree = {
            tid: len(task.predecessors) for tid, task in problem.tasks.items()
        }
        valid_start_time_preds = {tid: 0 for tid in problem.tasks}

        result = ScheduleResult()

        # Task IDs are 1-indexed in problem.tasks
        ready_tasks = [tid for tid, deg in current_in_degree.items() if deg == 0]

        while ready_tasks:
            # STEP A: SELECT TASK
            # priorities is 0-indexed, so we use tid-1
            selected_task_id = max(ready_tasks, key=lambda tid: priorities[tid - 1])
            ready_tasks.remove(selected_task_id)

            task = problem.tasks[selected_task_id]
            options = list(task.compatible_teams.items())

            if not options:
                continue

            # STEP B: SELECT TEAM
            selector_value = team_selectors[selected_task_id - 1]
            if selector_value >= 1.0:
                selector_value = 0.99999

            num_options = len(options)
            choice_index = int(math.floor(selector_value * num_options))

            assigned_team_id, task_cost = options[choice_index]

            # STEP C: CALCULATE START TIME
            start_lim_preds = valid_start_time_preds[selected_task_id]
            start_lim_team = current_team_times[assigned_team_id]

            actual_start_time = max(start_lim_preds, start_lim_team)
            actual_finish_time = actual_start_time + task.duration

            # STEP D: UPDATE STATE
            current_team_times[assigned_team_id] = actual_finish_time

            result.assignments.append(
                Assignment(selected_task_id, assigned_team_id, actual_start_time)
            )
            result.total_cost += task_cost
            result.makespan = max(result.makespan, actual_finish_time)
            result.scheduled_count += 1

            # Unlock Successors
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
        """
        Hierarchical Objective:
        1. Maximize Scheduled Tasks
        2. Minimize Makespan
        3. Minimize Cost
        """
        W1 = 10000000  # Priority 1
        W2 = 1000  # Priority 2
        W3 = 1  # Priority 3

        penalty_unscheduled = (problem.num_tasks - result.scheduled_count) * W1
        score_time = result.makespan * W2
        score_cost = result.total_cost * W3

        return penalty_unscheduled + score_time + score_cost

    def run(self, problem: ProblemInstance) -> Schedule:
        random.seed(self.seed)
        start_time_pso = time.time()

        dim = 2 * problem.num_tasks
        swarm = [Particle(dim) for _ in range(self.swarm_size)]

        global_best_fitness = float("inf")
        global_best_result: Optional[ScheduleResult] = None
        global_best_position: Optional[List[float]] = None

        for iteration in range(self.max_iterations):
            if time.time() - start_time_pso >= self.time_limit:
                break

            for particle in swarm:
                # 1. Decode & Evaluate
                result = self._decode_particle(particle.position, problem)
                fitness = self._calculate_fitness(result, problem)

                # 2. Update Personal Best
                if fitness < particle.best_fitness:
                    particle.best_fitness = fitness
                    particle.best_position = list(particle.position)
                    particle.best_result = result

                # 3. Update Global Best
                if fitness < global_best_fitness:
                    global_best_fitness = fitness
                    global_best_position = list(particle.position)
                    global_best_result = result

            if global_best_position is None:
                continue

            # 4. Move Particles
            for particle in swarm:
                for i in range(dim):
                    r1 = random.random()
                    r2 = random.random()

                    # Velocity update
                    vel_cognitive = (
                        self.c1
                        * r1
                        * (particle.best_position[i] - particle.position[i])
                    )
                    vel_social = (
                        self.c2 * r2 * (global_best_position[i] - particle.position[i])
                    )

                    particle.velocity[i] = (
                        (self.w * particle.velocity[i]) + vel_cognitive + vel_social
                    )

                    # Position update
                    particle.position[i] += particle.velocity[i]

                    # Boundary clamping [0.0, 1.0]
                    if particle.position[i] < 0.0:
                        particle.position[i] = 0.0
                        particle.velocity[i] *= -0.5  # Wall bounce
                    elif particle.position[i] > 1.0:
                        particle.position[i] = 1.0
                        particle.velocity[i] *= -0.5  # Wall bounce

        if global_best_result:
            return Schedule(assignments=global_best_result.assignments)
        return Schedule(assignments=[])
