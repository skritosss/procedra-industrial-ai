from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import TypedDict, cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.evaluation.safety import analyze_untrusted_context  # noqa: E402


DEFAULT_CORPUS = PROJECT_ROOT / "examples" / "safety_adversarial_corpus.json"
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "safety_adversarial_report.json"


class CorpusCase(TypedDict):
    id: str
    language: str
    context: str
    expected_codes: list[str]


def evaluate_corpus(corpus_path: Path = DEFAULT_CORPUS) -> dict[str, object]:
    cases = cast(list[CorpusCase], json.loads(corpus_path.read_text(encoding="utf-8")))
    rows: list[dict[str, object]] = []
    true_positive_labels = 0
    false_positive_labels = 0
    false_negative_labels = 0

    for case in cases:
        findings = analyze_untrusted_context(case["context"])
        expected = set(case["expected_codes"])
        actual = {finding.code for finding in findings}
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        true_positive_labels += len(expected & actual)
        false_positive_labels += len(unexpected)
        false_negative_labels += len(missing)
        rows.append(
            {
                "id": case["id"],
                "language": case["language"],
                "expected_codes": sorted(expected),
                "actual_codes": sorted(actual),
                "missing_codes": missing,
                "unexpected_codes": unexpected,
                "passed": not missing and not unexpected,
            }
        )

    precision_denominator = true_positive_labels + false_positive_labels
    recall_denominator = true_positive_labels + false_negative_labels
    precision = true_positive_labels / precision_denominator if precision_denominator else 1.0
    recall = true_positive_labels / recall_denominator if recall_denominator else 1.0
    failed = [row["id"] for row in rows if not row["passed"]]
    return {
        "corpus": str(corpus_path),
        "case_count": len(cases),
        "hostile_case_count": sum(1 for case in cases if case["expected_codes"]),
        "benign_case_count": sum(1 for case in cases if not case["expected_codes"]),
        "passed_case_count": len(cases) - len(failed),
        "failed_case_ids": failed,
        "true_positive_labels": true_positive_labels,
        "false_positive_labels": false_positive_labels,
        "false_negative_labels": false_negative_labels,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the deterministic safety detector corpus")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    report = evaluate_corpus(args.corpus)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "SAFETY_EVAL "
        f"passed={report['passed_case_count']}/{report['case_count']} "
        f"precision={report['precision']:.4f} recall={report['recall']:.4f} "
        f"fp={report['false_positive_labels']} fn={report['false_negative_labels']}"
    )
    return 0 if not report["failed_case_ids"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
