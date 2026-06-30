try:
    from . import agent  # noqa
except ModuleNotFoundError as exc:
    if exc.name not in {"agentkit", "veadk"}:
        raise
