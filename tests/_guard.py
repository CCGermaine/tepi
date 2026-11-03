"""Raise when a test reads the checkout's config.json."""

from pathlib import Path

import tepi.deck as deck

_REPO_CONFIG = Path(__file__).resolve().parents[1] / "config.json"
_load_config = deck.load_config


def _load_config_guard(path):
    if Path(path).resolve() == _REPO_CONFIG.resolve():
        raise AssertionError(f"A test opened the repo config at {path}. Pass a temp config instead.")
    return _load_config(path)


if not getattr(_load_config, "_tepi_guards_repo_config", False):
    _load_config_guard._tepi_guards_repo_config = True
    deck.load_config = _load_config_guard
