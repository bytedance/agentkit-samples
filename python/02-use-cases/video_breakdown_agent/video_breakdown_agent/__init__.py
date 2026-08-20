import importlib

from .utils.model_config import configure_model_environment

configure_model_environment()

agent = importlib.import_module(".agent", __name__)

__all__ = [
    "agent",
]
