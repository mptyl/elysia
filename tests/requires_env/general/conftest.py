import pytest
from elysia.util.dummy_adapter import DummyAdapter
from dspy import configure, ChatAdapter
import dspy


# @pytest.fixture(autouse=True, scope="module")
# def use_dummy_adapter():

#     prev_adapter = dspy.settings.adapter
#     configure(adapter=DummyAdapter())
#     yield
#     configure(adapter=prev_adapter)
