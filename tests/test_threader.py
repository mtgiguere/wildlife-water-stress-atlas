import threading
import time
import unittest

# We import the class we are about to create. This test will fail until we do.
from wildlife_water_stress_atlas.utils.generic_threader import GenericThreader


# --- Test Setup ---
# We create a mock client that perfectly imitates the real one for testing.
# It has a 'query' method, just like your WFSSoapClient and CSWRestClient.
class MockWfsClient:
    def __init__(self, client_id: str):
        self.client_id = client_id
        # We can even track if the 'close' method was called
        self.close_called = False

    def query(self, filters: dict, **kwargs) -> list:
        """A mock version of the client's query method."""

        # Simulate work/network latency
        time.sleep(0.1)

        # Log which thread is running which job
        print(f"  [Thread: {threading.get_ident()}] - Running query for client '{self.client_id}' with filters: {filters}")

        # Return a predictable result for testing
        return [{"id": self.client_id, "filter": filters.get("cql_filter", "N/A")}]

    def close(self):
        """Mocked close method."""
        self.close_called = True
        print(f"  [Thread: {threading.get_ident()}] - Closing client '{self.client_id}'")


# --- The Test Case ---
class TestGenericThreader(unittest.TestCase):
    def test_run_jobs_and_collect_results(self):
        """
        Tests that the GenericThreader can execute multiple 'query' jobs
        across different client instances and aggregate the results.
        """
        print("\n--- Running test_run_jobs_and_collect_results ---")

        # 1. Setup: Create mock clients and define the jobs
        client_1 = MockWfsClient("Client-A")
        client_2 = MockWfsClient("Client-B")

        # The 'jobs' list now contains tuples of (function, args, kwargs)
        # This matches the signature of the real 'query' method.
        jobs_to_run = [
            (
                client_1.query,
                [],
                {"filters": {"cql_filter": "road"}, "max_features": 100},
            ),
            (
                client_2.query,
                [],
                {"filters": {"cql_filter": "building"}, "max_features": 50},
            ),
            (
                client_1.query,
                [],
                {"filters": {"cql_filter": "parcel"}, "max_features": 200},
            ),
        ]

        # 2. Execution: Instantiate and run the threader
        # We are defining the interface for our threader class here.
        threader = GenericThreader(jobs=jobs_to_run)
        results = threader.run()

        # 3. Assertion: Verify the results
        self.assertEqual(len(results), 3, "Should have received results from all 3 jobs.")

        # Check the content of the results
        result_filters = [res[0]["filter"] for res in results]
        self.assertIn("road", result_filters)
        self.assertIn("building", result_filters)
        self.assertIn("parcel", result_filters)

        print("--- Test Passed ---")


def test_worker_stores_exception_on_error():
    """GenericThreader stores exception in results when a job raises."""
    from wildlife_water_stress_atlas.utils.generic_threader import GenericThreader

    def failing_job():
        raise ValueError("something went wrong")

    threader = GenericThreader(jobs=[(failing_job, [], {})])
    results = threader.run()

    assert isinstance(results[0], ValueError)
    assert str(results[0]) == "something went wrong"


# This allows the test to be run from the command line
if __name__ == "__main__":
    unittest.main(verbosity=2)
