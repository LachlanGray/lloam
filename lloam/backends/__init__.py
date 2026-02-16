from typing import Callable, Tuple


def _load_openai_backend() -> Callable:
    from .openai import stream_chat_completion as stream_openai_chat_completion

    return stream_openai_chat_completion


def _load_anthropic_backend() -> Callable:
    try:
        from .anthropic import stream_chat_completion as stream_anthropic_chat_completion
    except ImportError as e:
        raise ImportError(
            "Anthropic backend requires the 'anthropic' package. "
            "Install it with `pip install anthropic`."
        ) from e

    return stream_anthropic_chat_completion


_BACKEND_LOADERS = {
    "openai": _load_openai_backend,
    "anthropic": _load_anthropic_backend,
}


def parse_model_slug(model: str) -> Tuple[str, str]:
    if not isinstance(model, str) or model.strip() == "":
        raise ValueError("model must be a non-empty string")

    model = model.strip()
    if "/" not in model:
        # Backwards-compatible fallback.
        return "openai", model

    backend, provider_model = model.split("/", 1)
    backend = backend.strip().lower()
    provider_model = provider_model.strip()

    if not backend or not provider_model:
        raise ValueError(f"Invalid model slug '{model}'. Expected '<backend>/<model>'")

    return backend, provider_model


def get_backend(model: str) -> Tuple[Callable, str]:
    backend_name, backend_model = parse_model_slug(model)
    backend_loader = _BACKEND_LOADERS.get(backend_name)

    if backend_loader is None:
        supported = ", ".join(sorted(_BACKEND_LOADERS.keys()))
        raise ValueError(f"Unknown backend '{backend_name}'. Supported backends: {supported}")

    backend = backend_loader()
    return backend, backend_model
