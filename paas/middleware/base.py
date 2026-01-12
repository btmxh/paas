from abc import ABC, abstractmethod
from typing import Optional, Protocol

from paas.models import ProblemInstance, Schedule


class Runnable(Protocol):
    def run(self, problem: ProblemInstance) -> Schedule: ...


class Middleware(ABC):
    """
    Abstract middleware class.
    """

    def __init__(self, next_runnable: Optional[Runnable] = None):
        self.next = next_runnable

    @abstractmethod
    def run(self, problem: ProblemInstance) -> Schedule:
        """
        Process the problem and return a schedule.
        """
        pass


class MapProblem(Middleware):
    """
    Middleware specialized for transforming the problem instance
    before passing it to the next handler.
    """

    def run(self, problem: ProblemInstance) -> Schedule:
        new_problem = self.map_problem(problem)
        if self.next:
            return self.next.run(new_problem)
        raise ValueError(
            "MapProblem middleware requires a next handler to process the problem."
        )

    @abstractmethod
    def map_problem(self, problem: ProblemInstance) -> ProblemInstance:
        """
        Transform the problem instance.
        """
        pass


class MapResult(Middleware):
    """
    Middleware specialized for refining the result (schedule)
    returned by the next handler.
    """

    def run(self, problem: ProblemInstance) -> Schedule:
        if not self.next:
            raise ValueError(
                "MapResult middleware requires a next handler to produce a result."
            )

        result = self.next.run(problem)
        return self.map_result(result)

    @abstractmethod
    def map_result(self, result: Schedule) -> Schedule:
        """
        Refine the result.
        """
        pass
