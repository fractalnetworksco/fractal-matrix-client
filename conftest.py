import pytest
from fractal.matrix.async_client import FractalAsyncClient


def test_fractal_async_client():
    test_object = FractalAsyncClient()
    print("work")
    return test_object


@pytest.fixture()
def mock_async_context_manager():
    class AsyncContextManager:
        async def __aenter__(self):
            # Perform setup actions here
            yield "async_context_value"

        async def __aexit__(self, exc_type, exc, tb):
            # Perform cleanup actions here
            pass

    return AsyncContextManager
