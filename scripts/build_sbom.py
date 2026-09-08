"""Produce a dependency inventory a customer's security team can act on.

Two files, because they answer two different questions.

`sbom.cyclonedx.json` lists what the application is made of, in CycloneDX — the
format a security team feeds into its own tooling. `sbom_report.md` says the
same thing in a form a person reads, plus the vulnerability status at the moment
it ran.

Both are generated, never committed: an inventory checked into a repository is
wrong the day a dependency moves, and a stale inventory is worse than none.

The boundary is stated in the report rather than left for the reader to
discover: this covers the pinned Python dependencies, not the operating-system
packages of the base image. Those need a container scanner, which this project
does not carry.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = PROJECT_ROOT / "requirements.txt"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "generated" / "sbom"


def _run(arguments: list[str]) -> tuple[int, str, str]:
    completed = subprocess.run(
        [sys.executable, "-m", "pip_audit", *arguments],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode, completed.stdout, completed.stderr


def _normalized_project_name(name: str) -> str:
    """PEP 503 normalisation: the form a Package URL is built from."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _add_package_urls(components: list[dict]) -> None:
    """Give every component a Package URL.

    pip-audit emits name and version but no `purl`, and a security team's tooling
    matches on `purl`. Without it the inventory is readable by a person and
    close to useless to a scanner, which is the opposite of why it is produced.

    The mapping is mechanical for PyPI, so this adds no judgement of its own.
    """
    for component in components:
        name = component.get("name")
        version = component.get("version")
        if not name or not version or "purl" in component:
            continue
        component["purl"] = f"pkg:pypi/{_normalized_project_name(name)}@{version}"


def _pinned_count() -> int:
    lines = REQUIREMENTS.read_text(encoding="utf-8").splitlines()
    return sum(1 for line in lines if line.strip() and not line.lstrip().startswith("#"))


def build(output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    sbom_path = output_dir / "sbom.cyclonedx.json"
    report_path = output_dir / "sbom_report.md"

    code, stdout, stderr = _run(["-r", str(REQUIREMENTS), "--format", "cyclonedx-json"])
    if code not in (0, 1) or not stdout.strip():
        # 0 = clean, 1 = vulnerabilities found; both still emit a document.
        print(stderr or "pip-audit produced no document", file=sys.stderr)
        return 2
    document = json.loads(stdout)
    components = document.get("components", [])
    _add_package_urls(components)
    sbom_path.write_text(json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8")

    audit_code, audit_stdout, audit_stderr = _run(["-r", str(REQUIREMENTS), "--format", "markdown"])
    findings = audit_stdout.strip() or "Уязвимостей не найдено."

    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    report_path.write_text(
        "\n".join(
            [
                "# Состав зависимостей и статус уязвимостей",
                "",
                f"Сформировано: {generated_at}",
                f"Источник: `requirements.txt`, закреплённых строк — {_pinned_count()}",
                f"Компонентов в перечне: {len(components)}",
                "",
                "Машиночитаемый перечень в формате CycloneDX — `sbom.cyclonedx.json`.",
                "",
                "## Что покрыто",
                "",
                "Python-зависимости приложения, закреплённые по версиям в",
                "`requirements.txt`, и их транзитивные зависимости.",
                "",
                "## Что не покрыто",
                "",
                "Пакеты операционной системы базового образа: Debian, ffmpeg,",
                "библиотеки OpenCV. Для них нужен сканер контейнеров, которого в",
                "проекте нет. Если это требование заказчика, оно решается сканером",
                "на стороне заказчика по собранному образу либо добавлением шага",
                "в конвейер сборки по согласованию.",
                "",
                "## Уязвимости на момент формирования",
                "",
                findings,
                "",
                "## Как воспроизвести",
                "",
                "```bash",
                "make sbom",
                "```",
                "",
                "Файлы не хранятся в репозитории намеренно: перечень устаревает в",
                "день изменения любой зависимости, а устаревший перечень хуже",
                "отсутствующего.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"компонентов: {len(components)}")
    print(f"перечень: {sbom_path}")
    print(f"отчёт:    {report_path}")
    if audit_code == 1:
        print("ВНИМАНИЕ: найдены уязвимости, см. отчёт", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the dependency inventory")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    arguments = parser.parse_args()
    return build(arguments.output)


if __name__ == "__main__":
    raise SystemExit(main())
