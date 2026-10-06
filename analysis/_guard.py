"""Prevent numerical execution before the milestone 0.1 gate is accepted."""


def refuse_simulation(entrypoint: str) -> None:
    raise SystemExit(
        f"{entrypoint}: simulation is intentionally disabled in Repo v0.1. "
        "Accept the skeleton, input schema, variants and QA contract before implementation."
    )
