import pytest
from aioresponses import aioresponses
from fractal.matrix.async_client import FractalAsyncClient


@pytest.fixture
def test_fractal_async_client():
    test_object = FractalAsyncClient()
    print("work")
    return test_object


@pytest.fixture
def mock_aiohttp_client():
    with aioresponses() as m:
        yield m
