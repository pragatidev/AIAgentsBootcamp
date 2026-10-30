"""Keep the desk answering when a model call fails: retry what might pass, fall back on what will not."""

from __future__ import annotations

from langchain.agents.middleware import ModelFallbackMiddleware, ModelRetryMiddleware

# A request the provider refused as bad, unauthorised, forbidden or not found fails the same way every time.
PERMANENT_STATUS = {400, 401, 403, 404}


def is_transient(exc: BaseException) -> bool:
    """True when the same call might pass if tried again; False for a status that will fail the same way."""
    return getattr(exc, "status_code", None) not in PERMANENT_STATUS


def resilience(fallback_model) -> list:
    """Retry the same model on a transient fault, then fall back to a model you trust.

    The fallback is listed first, so it is the outer layer: the retry runs inside it, and
    on_failure="error" makes an exhausted retry raise, which is what lets the fallback run.
    """
    return [
        ModelFallbackMiddleware(fallback_model),
        ModelRetryMiddleware(
            max_retries=2,
            retry_on=is_transient,
            on_failure="error",
            initial_delay=0.1,
            backoff_factor=0.0,
            jitter=False,
        ),
    ]
