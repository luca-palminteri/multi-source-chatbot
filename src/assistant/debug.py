"""Opt-in diagnostics without prompts, tool arguments, credentials, or error text."""
from contextlib import contextmanager
import logging
import time
import traceback

logger = logging.getLogger("assistant.debug")


def configure(enabled=False):
    if enabled:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s DEBUG %(message)s", "%H:%M:%S"))
        if not logger.handlers:
            logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False


def failure_details(exc):
    details = {"error_type": type(exc).__name__}
    current = exc
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        for attribute in ("status_code", "code"):
            value = getattr(current, attribute, None)
            if isinstance(value, int) and not isinstance(value, bool):
                details.setdefault("status_code", value)
        payload = getattr(current, "details", None)
        if isinstance(payload, dict):
            error = payload.get("error", payload)
            for item in error.get("details", []) if isinstance(error, dict) else []:
                if not isinstance(item, dict):
                    continue
                delay = item.get("retryDelay")
                if isinstance(delay, str):
                    import re
                    if re.fullmatch(r"[0-9.]+s", delay):
                        details["retry_after_seconds"] = float(delay[:-1])
                for violation in item.get("violations", []):
                    if not isinstance(violation, dict):
                        continue
                    metric = violation.get("quotaMetric", "")
                    import re
                    if isinstance(metric, str) and re.fullmatch(r"[A-Za-z0-9_./-]+", metric):
                        details.setdefault("quota_metrics", []).append(metric)
        current = current.__cause__ or current.__context__
    cause = exc.__cause__ or exc.__context__
    if cause is not None:
        details["cause_type"] = type(cause).__name__
    return details


def log_failure(stage, exc):
    logger.debug("%s failed: %s", stage, failure_details(exc))
    # Never log exception messages or source lines: either can contain secrets.
    for frame in traceback.extract_tb(exc.__traceback__):
        from pathlib import Path
        logger.debug("  at %s:%s in %s", Path(frame.filename).name, frame.lineno, frame.name)


@contextmanager
def stage(name):
    started = time.monotonic()
    logger.debug("%s started", name)
    try:
        yield
    except Exception as exc:
        log_failure(name, exc)
        raise
    finally:
        logger.debug("%s finished after %.1fs", name, time.monotonic() - started)


def traced(name):
    from functools import wraps

    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            with stage(name):
                return function(*args, **kwargs)
        return wrapped
    return decorate
