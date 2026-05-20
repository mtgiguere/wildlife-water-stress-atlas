"""generic_threader.py

Simple parallel job runner using Python's threading module.

Used to fan out multiple WFS/CSW queries simultaneously (e.g. one thread per
sensor family or date chunk) and collect results in order. Not intended for
CPU-bound work — use this only for I/O-bound tasks like network queries.
"""

import threading
from typing import Any, Callable, Dict, List, Tuple


class GenericThreader:
    """
    A generic threading utility to run a list of functions in parallel
    and collect their results.
    """

    def __init__(self, jobs: List[Tuple[Callable, List, Dict]]):
        """
        Initializes the threader with a list of jobs.

        Args:
            jobs (List[Tuple[Callable, List, Dict]]): A list of jobs to run.
                Each job is a tuple containing:
                - The function to execute (e.g., client.query).
                - A list of positional arguments for the function.
                - A dictionary of keyword arguments for the function.
        """
        self.jobs = jobs
        self.results = [None] * len(jobs)  # Pre-allocate list to store results by index
        self.threads = []

    def _worker(self, index: int, func: Callable, args: List, kwargs: Dict):
        """The target function for each thread."""
        try:
            # Execute the function and store the result in the correct position
            result = func(*args, **kwargs)
            self.results[index] = result
        except Exception as e:
            # Store the exception as the result so it can be handled
            print(f"  [Thread: {threading.get_ident()}] - ERROR in worker: {e}")
            self.results[index] = e

    def run(self) -> List[Any]:
        """
        Starts the threads for all jobs, waits for them to complete,
        and returns the collected results.

        Returns:
            List[Any]: A list containing the return value of each job. The order
                       of the results matches the order of the initial jobs list.
        """
        # Create and start a thread for each job
        for i, (func, args, kwargs) in enumerate(self.jobs):
            thread = threading.Thread(target=self._worker, args=(i, func, args, kwargs))
            self.threads.append(thread)
            thread.start()

        # Wait for all threads to finish their execution
        for thread in self.threads:
            thread.join()

        return self.results
