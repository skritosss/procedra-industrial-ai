"""Fill a local instance with believable demo content before a walkthrough.

A recording that opens on empty lists spends its first minute explaining that the
product does work, really. This creates the state a real user would have after a
week: a few saved instructions across profiles, one already through review, an
execution record, an uploaded reference document, and the audit trail that
accumulated along the way.

Everything written here is synthetic and safe to show. The scenarios are the same
narrow manufacturing tasks used elsewhere in the repository, so nothing on screen
implies a customer, a pilot, or a validated result.

    make run                     # in one terminal
    python scripts/seed_demo_data.py

Re-running is safe: instruction identifiers are derived from the title, so the
same scenario saves as a new version of the same instruction rather than a
duplicate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_BASE_URL = "http://127.0.0.1:8000"

SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "task": "Подготовить рабочее место оператора перед запуском ленточнопильного станка",
        "industry_profile": "manufacturing",
        "instruction_type": "workplace_preparation",
        "department": "Заготовительный участок",
        "equipment": "Ленточнопильный станок",
        "operation_name": "Подготовка станка к запуску",
        "technical_context": (
            "Перед запуском проверить ограждения, аварийную остановку, натяжение полотна, "
            "отсутствие посторонних предметов и состояние зоны резания. Точные параметры "
            "подтверждаются по паспорту оборудования и локальной карте операции."
        ),
    },
    {
        "task": "Провести осмотр защитных ограждений пресса перед началом смены",
        "industry_profile": "occupational_safety",
        "instruction_type": "inspection",
        "department": "Кузнечно-прессовый участок",
        "equipment": "Кривошипный пресс",
        "operation_name": "Осмотр ограждений",
        "technical_context": (
            "Осмотреть неподвижные и блокировочные ограждения, проверить срабатывание "
            "блокировки, зафиксировать замечания в журнале участка."
        ),
    },
    {
        "task": "Подготовить участок к проведению огневых работ",
        "industry_profile": "construction",
        "instruction_type": "general",
        "department": "Ремонтно-механический участок",
        "equipment": "Сварочный пост",
        "operation_name": "Подготовка к огневым работам",
        "technical_context": (
            "Оформить наряд-допуск, убрать горючие материалы, обеспечить средства "
            "пожаротушения и назначить наблюдающего."
        ),
    },
)

REFERENCE_DOCUMENT = """Регламент участка: подготовка оборудования к запуску

1. Перед началом смены оператор осматривает рабочее место и убеждается в
   отсутствии посторонних предметов в зоне обслуживания.
2. Защитные ограждения должны быть установлены и закреплены. Работа со снятым
   ограждением запрещена.
3. Аварийная остановка проверяется перед каждым запуском. При отказе оборудование
   не запускается, мастер уведомляется немедленно.
4. Результаты осмотра фиксируются в журнале участка с указанием даты, смены и
   фамилии оператора.
5. Точные режимы, допуски и периодичность обслуживания принимаются по паспорту
   оборудования и утверждённой карте операции.
"""


def call(
    method: str,
    url: str,
    token: str | None = None,
    body: dict | None = None,
    raw: bytes | None = None,
    content_type: str | None = None,
) -> tuple[int, Any]:
    data = raw if raw is not None else (json.dumps(body).encode("utf-8") if body is not None else None)
    request = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", content_type or "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = response.read()
            try:
                return int(response.status), json.loads(payload)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return int(response.status), payload
    except urllib.error.HTTPError as error:
        payload = error.read()
        try:
            return int(error.code), json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return int(error.code), payload
    except (urllib.error.URLError, OSError, TimeoutError) as error:
        return 0, str(error)


def sign_in(base_url: str, email: str, password: str, full_name: str) -> str:
    code, body = call(
        "POST",
        f"{base_url}/api/auth/register",
        body={"email": email, "full_name": full_name, "password": password, "role": "admin"},
    )
    if code in (200, 201) and isinstance(body, dict) and body.get("access_token"):
        return str(body["access_token"])
    code, body = call("POST", f"{base_url}/api/auth/login", body={"email": email, "password": password})
    if code == 200 and isinstance(body, dict) and body.get("access_token"):
        return str(body["access_token"])
    raise SystemExit(f"Could not sign in as {email}: {code} {str(body)[:300]}")


def upload_reference_document(base_url: str, token: str) -> bool:
    boundary = "----procedra-seed"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="file"; filename="reglament-uchastka.md"\r\n',
            b"Content-Type: text/markdown\r\n\r\n",
            REFERENCE_DOCUMENT.encode("utf-8"),
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    code, _ = call(
        "POST",
        f"{base_url}/api/documents/upload",
        token=token,
        raw=body,
        content_type=f"multipart/form-data; boundary={boundary}",
    )
    return code == 200


def seed(base_url: str, email: str, password: str) -> int:
    token = sign_in(base_url, email, password, "Демонстрационный администратор")
    print(f"signed in as {email}")

    if upload_reference_document(base_url, token):
        print("uploaded reference document")
    else:
        print("reference document already present or upload refused")

    saved: list[tuple[str, int, dict]] = []
    for index, scenario in enumerate(SCENARIOS, start=1):
        code, generated = call(
            "POST",
            f"{base_url}/api/instructions/generate-with-context",
            token=token,
            body={**scenario, "max_sources": 15},
        )
        if code != 200 or not isinstance(generated, dict):
            print(f"  scenario {index}: generation failed ({code})")
            continue
        code, stored = call(
            "POST", f"{base_url}/api/instructions/history", token=token, body={"payload": generated}
        )
        record = stored.get("record", {}) if isinstance(stored, dict) else {}
        instruction_id = record.get("instruction_id")
        version = record.get("version")
        if not instruction_id or version is None:
            print(f"  scenario {index}: save failed ({code})")
            continue
        score = generated.get("evaluation", {}).get("overall_score")
        print(f"  saved «{scenario['operation_name']}» v{version}, structure score {score}")
        saved.append((str(instruction_id), int(version), generated))

    if not saved:
        print("nothing was saved; is the server running with demo settings?")
        return 1

    # Take the first instruction the whole way through review and execution, so
    # the walkthrough has one document with real history rather than three
    # identical fresh drafts.
    instruction_id, version, payload = saved[0]
    quoted = urllib.parse.quote(instruction_id, safe="")

    code, _ = call(
        "PATCH",
        f"{base_url}/api/instructions/history/{quoted}/versions/{version}/workflow",
        token=token,
        body={
            "status": "expert_review",
            "reviewer": "Технолог участка",
            "reviewer_role": "technologist",
            "comment": "Передано на экспертную проверку в рамках демонстрационного сценария.",
        },
    )
    print("moved the first instruction to expert review" if code == 200 else f"  workflow failed ({code})")

    steps = [
        {"label": f"{step['number']}. {step['action']}", "completed": True}
        for step in payload["instruction"]["steps"]
    ]
    code, _ = call(
        "POST",
        f"{base_url}/api/instructions/history/{quoted}/versions/{version}/execution",
        token=token,
        body={
            "executor": "Оператор смены",
            "notes": "Пробное исполнение в демонстрационном контуре, не производственный запуск.",
            "steps": steps,
            "quality_items": [],
        },
    )
    print("recorded an execution run" if code in (200, 201) else f"  execution failed ({code})")

    print("\nDemo data is in place. Open the web interface and start on the history tab.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--email", default="demo@procedra.local")
    parser.add_argument("--password", default="demo-password-2026")
    args = parser.parse_args()

    code, _ = call("GET", f"{args.base_url}/health")
    if code != 200:
        print(f"No server at {args.base_url} — start it with `make run` first.")
        return 1
    return seed(args.base_url, args.email, args.password)


if __name__ == "__main__":
    raise SystemExit(main())
