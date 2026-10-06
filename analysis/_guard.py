"""Prevent baseline execution until all required controlled inputs are present."""


def refuse_simulation(entrypoint: str) -> None:
    raise SystemExit(
        f"{entrypoint}: simulation is intentionally disabled in Repo v0.1. "
        "The energy code is unit-tested, but the locked EPW and downstream "
        "lifecycle/decision modules are not yet execution-ready."
    )
