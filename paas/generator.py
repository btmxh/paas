import random
from .models import ProblemInstance, Task, Team


def generate_instance(
    n_tasks: int,
    n_teams: int,
    dependency_ratio: float = 0.2,
    compatibility_ratio: float = 0.5,
    max_duration: int = 100,
    max_start_time: int = 100,
    max_cost: int = 100,
    seed: int = None,
) -> ProblemInstance:
    if seed is not None:
        random.seed(seed)

    # 1. Generate dependencies (DAG)
    # We can ensure DAG by only allowing i -> j if i < j
    dependencies = []
    # Maximum possible dependencies is N*(N-1)/2
    # We use dependency_ratio to determine how many to actually create
    for i in range(1, n_tasks + 1):
        for j in range(i + 1, n_tasks + 1):
            if random.random() < dependency_ratio:
                dependencies.append((i, j))

    # 2. Generate durations
    durations = [random.randint(1, max_duration) for _ in range(n_tasks)]

    # 3. Generate teams and their start times
    team_start_times = [random.randint(0, max_start_time) for _ in range(n_teams)]
    teams = {
        j: Team(id=j, available_from=team_start_times[j - 1])
        for j in range(1, n_teams + 1)
    }

    # 4. Generate task-team compatibilities
    tasks = {i: Task(id=i, duration=durations[i - 1]) for i in range(1, n_tasks + 1)}
    for u, v in dependencies:
        tasks[v].predecessors.append(u)
        tasks[u].successors.append(v)

    compatibilities = []
    for i in range(1, n_tasks + 1):
        # Ensure each task is compatible with at least one team
        guaranteed_team = random.randint(1, n_teams)
        tasks[i].compatible_teams[guaranteed_team] = random.randint(1, max_cost)
        compatibilities.append(
            (i, guaranteed_team, tasks[i].compatible_teams[guaranteed_team])
        )

        for j in range(1, n_teams + 1):
            if j == guaranteed_team:
                continue
            if random.random() < compatibility_ratio:
                cost = random.randint(1, max_cost)
                tasks[i].compatible_teams[j] = cost
                compatibilities.append((i, j, cost))

    return ProblemInstance(
        num_tasks=n_tasks, num_teams=n_teams, tasks=tasks, teams=teams
    )


def serialize_instance(instance: ProblemInstance) -> str:
    lines = []

    # N Q
    dependencies = []
    for task_id, task in instance.tasks.items():
        for succ in task.successors:
            dependencies.append((task_id, succ))

    lines.append(f"{instance.num_tasks} {len(dependencies)}")

    # Q lines of dependencies
    for u, v in dependencies:
        lines.append(f"{u} {v}")

    # N durations
    durations = [instance.tasks[i].duration for i in range(1, instance.num_tasks + 1)]
    lines.append(" ".join(map(str, durations)))

    # M
    lines.append(str(instance.num_teams))

    # M start times
    start_times = [
        instance.teams[j].available_from for j in range(1, instance.num_teams + 1)
    ]
    lines.append(" ".join(map(str, start_times)))

    # K
    compatibilities = []
    for task_id, task in instance.tasks.items():
        for team_id, cost in task.compatible_teams.items():
            compatibilities.append((task_id, team_id, cost))

    lines.append(str(len(compatibilities)))

    # K lines of costs
    for i, j, c in compatibilities:
        lines.append(f"{i} {j} {c}")

    return "\n".join(lines)
