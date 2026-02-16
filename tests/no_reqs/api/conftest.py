import pytest
from elysia.util.dummy_adapter import DummyAdapter
from dspy import configure, ChatAdapter
import dspy


@pytest.fixture(autouse=True, scope="module")
def use_dummy_adapter():
    dummy_adapter = DummyAdapter()
    configure(adapter=dummy_adapter)

    yield

    configure(adapter=ChatAdapter())
