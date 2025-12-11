"""Compare bounded repair policies on planted synthetic transcript noise."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from voxwright.core import JSONValue, canonical_json
from voxwright.repair import RepairConfig, RepairOutcome, RepairStrategy, run_repair
from voxwright.reports import curve_chart_svg
from voxwright.scenarios import edit_tokens, schedule_scenario

NOISE_RATES = (0.0, 0.2, 0.4, 0.6)
POLICIES = {
    "cautious": RepairConfig(0.3, 0.5, 0.75, 0.95, 3),
    "permissive": RepairConfig(0.2, 0.35, 0.5, 0.7, 2),
}


@dataclass(frozen=True, slots=True)
class CurvePoint:
    noise_rate: float
    task_success: float
    repair_rate: float
    handoff_rate: float

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "noise_rate": self.noise_rate,
            "task_success": self.task_success,
            "repair_rate": self.repair_rate,
            "handoff_rate": self.handoff_rate,
        }


def repaired_task_succeeded(outcome: RepairOutcome, corrupted: bool) -> bool:
    if not outcome.resolved:
        return False
    accepted_without_repair = outcome.strategies == (RepairStrategy.ACCEPT,)
    return not corrupted or not accepted_without_repair


def measure_policy(seed: int, samples: int, config: RepairConfig) -> tuple[CurvePoint, ...]:
    points = []
    for noise_rate in NOISE_RATES:
        outcomes: list[RepairOutcome] = []
        successes = 0
        for offset in range(samples):
            scenario = schedule_scenario(seed + offset)
            planted = edit_tokens(
                scenario.transcript,
                seed * 10_000 + offset,
                deletion_rate=noise_rate / 2,
                insertion_rate=noise_rate / 2,
            )
            confidence = round(1.0 - noise_rate, 6)
            outcome = run_repair(
                (confidence, min(1.0, confidence + 0.4), 1.0),
                (planted.heard, planted.source),
                config,
            )
            outcomes.append(outcome)
            successes += repaired_task_succeeded(outcome, bool(planted.operations))
        points.append(
            CurvePoint(
                noise_rate,
                round(successes / samples, 6),
                round(sum(item.attempts > 0 for item in outcomes) / samples, 6),
                round(sum(item.handed_off for item in outcomes) / samples, 6),
            )
        )
    return tuple(points)


def run(output: Path, seed: int, samples: int) -> dict[str, JSONValue]:
    if seed < 0:
        raise ValueError("seed must be non-negative")
    if samples < 1:
        raise ValueError("samples must be positive")
    output.mkdir()
    curves = {
        name: [point.to_dict() for point in measure_policy(seed, samples, config)]
        for name, config in POLICIES.items()
    }
    summary: dict[str, JSONValue] = {
        "curves": curves,
        "noise_rates": list(NOISE_RATES),
        "policies": {name: config.to_dict() for name, config in POLICIES.items()},
        "samples_per_noise": samples,
        "seed": seed,
        "synthetic": True,
    }
    (output / "metrics.json").write_text(
        canonical_json(summary) + "\n", encoding="utf-8", newline="\n"
    )
    for policy_name, points in curves.items():
        success_points = tuple(
            (float(point["noise_rate"]), float(point["task_success"])) for point in points
        )
        repair_points = tuple(
            (float(point["noise_rate"]), float(point["repair_rate"])) for point in points
        )
        (output / f"{policy_name}-success.svg").write_text(
            curve_chart_svg(f"{policy_name} synthetic task success", success_points),
            encoding="utf-8",
            newline="\n",
        )
        (output / f"{policy_name}-repair.svg").write_text(
            curve_chart_svg(f"{policy_name} repair rate", repair_points),
            encoding="utf-8",
            newline="\n",
        )
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--samples", type=int, default=20)
    args = parser.parse_args(argv)
    print(canonical_json(run(args.output, args.seed, args.samples)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
