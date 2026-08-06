import platform


def get_device_with_fallback() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"

        if (
            platform.system() == "Darwin"
            and hasattr(torch.backends, "mps")
            and torch.backends.mps.is_available()
        ):
            return "mps"
    except Exception:
        pass

    return "cpu"
