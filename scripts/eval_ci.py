"""Eval harness in CI. Exit 1 when a tracked metric drops past the line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runners.golden import (  # noqa: E402
    BASELINE,
    LAST_RUN,
    parse_metrics_file,
    run_golden,
    write_metrics_file,
)

TRACKED = ("faithfulness", "context_recall", "refused_correctly")


def load_thresholds(path: Path) -> dict:
    import tomllib

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    tracked = dict(data.get("tracked") or {})
    max_drop = tracked.pop("max_drop", {})
    if not isinstance(max_drop, dict):
        max_drop = {name: float(max_drop) for name in TRACKED}
    reported = dict(data.get("reported") or {})
    floors = {name: float(tracked[name]) for name in TRACKED if name in tracked}
    drops = {name: float(max_drop.get(name, 0.08)) for name in TRACKED}
    return {"floors": floors, "max_drop": drops, "reported": reported}


def _delta(now: float, baseline: float) -> float:
    return now - baseline


def _verdict(name: str, now: float, baseline: float, thresholds: dict) -> str:
    floor = thresholds["floors"].get(name)
    drop = thresholds["max_drop"].get(name, 0.08)
    if floor is not None and now < floor:
        return "FAIL"
    if (baseline - now) > drop:
        return "FAIL"
    return "PASS"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DataFlow eval CI gate")
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="run with tests fixtures so CI needs no Ollama",
    )
    parser.add_argument(
        "--compare-to",
        default=str(BASELINE),
        help="baseline file. --compare-to eval/last_run.md is the mirror mistake",
    )
    parser.add_argument(
        "--thresholds",
        default=str(ROOT / "eval" / "thresholds.toml"),
    )
    parser.add_argument("--chunker", default="heading")
    parser.add_argument("--chunk-size", type=int, default=None)
    parser.add_argument("--retrieve-k", type=int, default=None)
    parser.add_argument(
        "--write-run",
        default=None,
        help="also write this run's numbers to a markdown file",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    thresholds_path = Path(args.thresholds)
    compare_path = Path(args.compare_to)
    thresholds = load_thresholds(thresholds_path)
    print("thresholds", thresholds_path.as_posix(), flush=True)
    print("compare_to", compare_path.as_posix(), flush=True)
    print("fixture", bool(args.fixture), flush=True)
    print("chunker", args.chunker, args.chunk_size, flush=True)

    report = run_golden(
        fixture=bool(args.fixture),
        chunker=str(args.chunker),
        chunk_size=args.chunk_size,
        retrieve_k=args.retrieve_k,
        progress=True,
    )
    write_metrics_file(LAST_RUN, int(report["unique_tickets"]), list(report["scores"]))
    if args.write_run:
        extra = Path(args.write_run)
        write_metrics_file(extra, int(report["unique_tickets"]), list(report["scores"]))
        print("wrote_run", extra.as_posix(), flush=True)

    # Default compares to the frozen baseline. --compare-to last_run.md is
    # the planted mirror mistake: the file was just written from this run,
    # so a number compared to itself never moves.
    if not compare_path.is_file():
        print("missing_compare_to", compare_path.as_posix(), flush=True)
        return 1
    baseline_metrics = parse_metrics_file(compare_path)
    now_metrics = parse_metrics_file(LAST_RUN)
    failed = False
    for name in TRACKED:
        now = float(now_metrics.get(name, 0.0))
        base = float(baseline_metrics.get(name, 0.0))
        delta = _delta(now, base)
        verdict = _verdict(name, now, base, thresholds)
        if verdict == "FAIL":
            failed = True
        print(
            f"{name} now {now:.3f} baseline {base:.3f} "
            f"delta {delta:+.3f} verdict {verdict}",
            flush=True,
        )
    latency_now = float(now_metrics.get("latency_s", 0.0))
    latency_base = float(baseline_metrics.get("latency_s", 0.0))
    print(
        f"latency_s now {latency_now:.2f} baseline {latency_base:.2f} "
        f"delta {_delta(latency_now, latency_base):+.2f} verdict REPORTED",
        flush=True,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
