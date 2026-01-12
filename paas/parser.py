from typing import TextIO, Iterator
from .models import ProblemInstance, Task, Team


def _token_iterator(input_stream: TextIO) -> Iterator[str]:
    for line in input_stream:
        for token in line.split():
            yield token


def parse_input(input_stream: TextIO) -> ProblemInstance:
    """
    Parses the problem input from the given text stream.

    The format is expected to be:
    - N Q
    - Q lines of dependencies (i j)
    - N durations
    - M
    - M start times
    - K
    - K lines of costs (i j c)
    """
    tokens = _token_iterator(input_stream)

    try:
        n_str = next(tokens)
        q_str = next(tokens)
    except StopIteration:
        raise ValueError("Input is empty or incomplete")

    N = int(n_str)
    Q = int(q_str)

    tasks = {i: Task(id=i, duration=0) for i in range(1, N + 1)}

    for _ in range(Q):
        u = int(next(tokens))
        v = int(next(tokens))
        tasks[v].predecessors.append(u)
        tasks[u].successors.append(v)

    for i in range(1, N + 1):
        d = int(next(tokens))
        tasks[i].duration = d

    M = int(next(tokens))

    teams = {}
    for j in range(1, M + 1):
        s = int(next(tokens))
        teams[j] = Team(id=j, available_from=s)

    K = int(next(tokens))

    for _ in range(K):
        task_id = int(next(tokens))
        team_id = int(next(tokens))
        cost = int(next(tokens))

        if task_id in tasks:
            tasks[task_id].compatible_teams[team_id] = cost

    return ProblemInstance(num_tasks=N, num_teams=M, tasks=tasks, teams=teams)
