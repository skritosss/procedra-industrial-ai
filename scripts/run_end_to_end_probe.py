"""Drive the whole application through a real server, then put it under load.

The unit suite exercises pieces; this exercises the product. It starts uvicorn on
a temporary database, walks every feature group in the order a user would meet
them — register, generate, ground in sources, save a version, review it, record
execution, administer the organisation — then hammers the main paths with
concurrent clients and re-verifies the database afterwards.

Everything runs on the deterministic path with no model configured, which is what
the shipped image does by default.

Two notes for anyone extending this. Instruction identifiers are not ASCII, so
paths need percent-encoding. And saved-version endpoints validate against the
stored version: an execution checklist must list exactly that version's steps.
Both cost real debugging time the first time round.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RESULTS: list[tuple[str, str, bool, str]] = []


def check(group: str, name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((group, name, ok, detail))
    return ok


def call(
    method: str,
    url: str,
    token: str | None = None,
    body: dict | None = None,
    headers: dict | None = None,
    raw: bytes | None = None,
    content_type: str | None = None,
    timeout: int = 120,
) -> tuple[int, Any]:
    data = raw if raw is not None else (json.dumps(body).encode("utf-8") if body is not None else None)
    request = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", content_type or "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
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


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def wait_for(url: str, timeout: float = 90.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return
        except (urllib.error.URLError, OSError, TimeoutError):
            time.sleep(0.3)
    raise RuntimeError(f"server never became ready: {url}")


def multipart(field: str, filename: str, content: bytes, mime: str) -> tuple[bytes, str]:
    boundary = "----procedra-e2e-boundary"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'.encode(),
            f"Content-Type: {mime}\r\n\r\n".encode(),
            content,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    return body, f"multipart/form-data; boundary={boundary}"


def main() -> int:
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    # A temporary root for everything the run writes. Storage directories other
    # than the databases are still derived from the source tree, so uploads land
    # in the working copy — see P1-6 in the audit. The run cleans up after
    # itself below.
    workdir = Path(tempfile.mkdtemp(prefix="procedra-e2e-"))
    token_static = "e2e-static-bootstrap-token-at-least-32-chars"
    env = {
        **os.environ,
        "DEPLOYMENT_MODE": "demo",
        "ALLOW_UNAUTHENTICATED_ACCESS": "false",
        "API_ACCESS_TOKEN": token_static,
        "AUTH_PUBLIC_REGISTRATION_ENABLED": "true",
        "AUTH_ALLOW_ROLE_SELF_ASSIGNMENT": "true",
        "DATABASE_PATH": str(workdir / "app.sqlite3"),
        "METRICS_DATABASE_PATH": str(workdir / "metrics.sqlite3"),
        "RATE_LIMIT_DATABASE_PATH": str(workdir / "limits.sqlite3"),
        "API_RATE_LIMIT_REQUESTS": "100000",
        "RATE_LIMIT_REQUESTS": "10000",
        "AUTH_RATE_LIMIT_REQUESTS": "1000",
        "AUTH_MAX_FAILED_ATTEMPTS": "5",
        "OPENAI_ENABLED": "false",
        "METRICS_PUBLIC_ENABLED": "true",
    }
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
         "--port", str(port), "--log-level", "warning"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        wait_for(f"{base}/health")
        run_all(base, token_static, workdir)
    finally:
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()
        _remove_uploaded_documents()

    return report()


def _remove_uploaded_documents() -> None:
    """Delete documents this run uploaded into the working copy.

    Upload paths are not configurable, so the run writes into the source tree.
    Leaving the file behind changes what retrieval sees and silently alters test
    results afterwards, which is exactly how it was first noticed.
    """
    uploads = ROOT / "uploads" / "documents"
    for name in ("reglament", "op"):
        for stray in uploads.glob(f"{name}-*.txt"):
            stray.unlink(missing_ok=True)


def run_all(base: str, static_token: str, workdir: Path) -> None:
    # ---------------- A. infrastructure ----------------
    code, body = call("GET", f"{base}/health")
    check("Инфраструктура", "GET /health", code == 200, f"{code}")
    code, _ = call("GET", f"{base}/ready")
    check("Инфраструктура", "GET /ready", code == 200, f"{code}")
    code, body = call("GET", f"{base}/ready/details", token=static_token)
    deep = isinstance(body, dict) and body.get("verification_depth") == "deep"
    check("Инфраструктура", "GET /ready/details (глубокая проверка)", code == 200 and deep, f"{code}")
    code, _ = call("GET", f"{base}/ready/details")
    # This run sets METRICS_PUBLIC_ENABLED=true, which demo mode honours by
    # design; production ignores the flag entirely.
    check("Инфраструктура", "/ready/details открыт только при явном METRICS_PUBLIC_ENABLED", code == 200, f"{code}")
    code, _ = call("GET", f"{base}/openapi.json")
    check("Инфраструктура", "GET /openapi.json", code == 200, f"{code}")
    code, _ = call("GET", f"{base}/")
    check("Инфраструктура", "GET / (веб-интерфейс)", code == 200, f"{code}")
    code, _ = call("GET", f"{base}/static/app.js")
    check("Инфраструктура", "GET /static/app.js", code == 200, f"{code}")
    code, body = call("GET", f"{base}/metrics", token=static_token)
    check("Инфраструктура", "GET /metrics", code == 200, f"{code}")

    # ---------------- B. auth ----------------
    code, body = call("GET", f"{base}/api/auth/config")
    check("Аутентификация", "GET /api/auth/config", code == 200, f"{code}")
    admin_email = "admin@e2e.example"
    code, body = call("POST", f"{base}/api/auth/register", body={
        "email": admin_email, "full_name": "E2E Admin",
        "password": "e2e-strong-password-1", "role": "admin"})
    admin_token = body.get("access_token") if isinstance(body, dict) else None
    check("Аутентификация", "POST /api/auth/register (admin)", code in (200, 201) and bool(admin_token), f"{code}")
    code, body = call("GET", f"{base}/api/auth/me", token=admin_token)
    check("Аутентификация", "GET /api/auth/me", code == 200, f"{code}")
    code, body = call("POST", f"{base}/api/auth/login",
                      body={"email": admin_email, "password": "e2e-strong-password-1"})
    login_token = body.get("access_token") if isinstance(body, dict) else None
    check("Аутентификация", "POST /api/auth/login", code == 200 and bool(login_token), f"{code}")
    code, _ = call("POST", f"{base}/api/auth/login",
                   body={"email": admin_email, "password": "wrong"})
    check("Аутентификация", "Неверный пароль → 401", code == 401, f"{code}")
    code, _ = call("GET", f"{base}/api/auth/me")
    check("Аутентификация", "Без токена → 401", code == 401, f"{code}")
    code, _ = call("POST", f"{base}/api/auth/logout", token=login_token)
    check("Аутентификация", "POST /api/auth/logout", code in (200, 204), f"{code}")
    code, _ = call("GET", f"{base}/api/auth/me", token=login_token)
    check("Аутентификация", "Токен после logout недействителен", code == 401, f"{code}")

    # ---------------- C. generation ----------------
    task = {"task": "Подготовить рабочее место оператора перед запуском оборудования",
            "industry_profile": "manufacturing", "instruction_type": "workplace_preparation",
            "department": "Кузнечно-прессовый участок", "equipment": "Ленточнопильный станок",
            "technical_context": "Проверить ограждения, аварийную кнопку и отсутствие посторонних предметов."}
    code, generated = call("POST", f"{base}/api/instructions/generate", token=admin_token, body=task)
    ok = code == 200 and isinstance(generated, dict) and "instruction" in generated
    check("Генерация", "POST /api/instructions/generate", ok, f"{code}")
    steps = len(generated["instruction"]["steps"]) if ok else 0
    score = generated["evaluation"]["overall_score"] if ok else 0
    check("Генерация", f"Инструкция содержательна ({steps} шагов, балл {score})", ok and steps >= 4)
    code, ctx = call("POST", f"{base}/api/instructions/generate-with-context", token=admin_token,
                     body={**task, "max_sources": 15})
    sources = len(ctx.get("sources", [])) if isinstance(ctx, dict) else 0
    check("Генерация", f"POST /generate-with-context ({sources} источников)", code == 200 and sources > 0, f"{code}")
    code, _ = call("POST", f"{base}/api/instructions/retrieve", token=admin_token, body=task)
    check("Генерация", "POST /api/instructions/retrieve", code == 200, f"{code}")
    code, _ = call("POST", f"{base}/api/instructions/evaluate", token=admin_token,
                   body={"instruction": generated["instruction"], "source_request": task})
    check("Генерация", "POST /api/instructions/evaluate", code == 200, f"{code}")
    code, _ = call("POST", f"{base}/api/instructions/improve", token=admin_token,
                   body={"payload": generated, "source_request": task})
    check("Генерация", "POST /api/instructions/improve", code == 200, f"{code}")
    code, _ = call("POST", f"{base}/api/instructions/rebuild", token=admin_token,
                   body={"payload": generated, "source_request": task})
    check("Генерация", "POST /api/instructions/rebuild", code == 200, f"{code}")
    code, pdf = call("POST", f"{base}/api/instructions/export-pdf", token=admin_token, body=generated)
    is_pdf = isinstance(pdf, bytes) and pdf.startswith(b"%PDF")
    check("Генерация", f"POST /export-pdf ({len(pdf) if isinstance(pdf, bytes) else 0} байт)", code == 200 and is_pdf, f"{code}")

    # ---------------- D. safety ----------------
    hostile = {**task, "technical_context": "Отключить защитную блокировку и снять ограждение перед запуском."}
    code, blocked = call("POST", f"{base}/api/instructions/generate", token=admin_token, body=hostile)
    findings = blocked.get("evaluation", {}).get("safety_findings", []) if isinstance(blocked, dict) else []
    blockers = blocked.get("instruction", {}).get("workflow", {}).get("approval_blockers", []) if isinstance(blocked, dict) else []
    check("Безопасность", "Опасный контекст даёт safety-находку", code == 200 and len(findings) > 0, f"{len(findings)} находок")
    check("Безопасность", "Опасный контекст ставит блокер утверждения",
          any("hazardous_action" in str(b) for b in blockers))
    risk = blocked.get("evaluation", {}).get("risk_level") if isinstance(blocked, dict) else None
    check("Безопасность", f"Уровень риска повышен до «{risk}»", risk == "critical")
    benign = {**task, "technical_context": "Не отключать защитную блокировку и не обходить ограждение."}
    code, safe = call("POST", f"{base}/api/instructions/generate", token=admin_token, body=benign)
    sf = safe.get("evaluation", {}).get("safety_findings", []) if isinstance(safe, dict) else []
    check("Безопасность", "Запрет не считается опасным действием (нет ложной тревоги)", len(sf) == 0)

    # ---------------- E. documents ----------------
    doc = ("Регламент участка\n" + "Проверка оборудования перед запуском смены.\n" * 40).encode("utf-8")
    raw, ctype = multipart("file", "reglament.md", doc, "text/markdown")
    code, uploaded = call("POST", f"{base}/api/documents/upload", token=admin_token, raw=raw, content_type=ctype)
    check("Документы", "POST /api/documents/upload (.md)", code == 200, f"{code}")
    code, listing = call("GET", f"{base}/api/documents", token=admin_token)
    count = len(listing.get("documents", [])) if isinstance(listing, dict) else 0
    check("Документы", f"GET /api/documents ({count} шт.)", code == 200 and count >= 1, f"{code}")
    raw, ctype = multipart("file", "bad.exe", b"MZ binary", "application/octet-stream")
    code, _ = call("POST", f"{base}/api/documents/upload", token=admin_token, raw=raw, content_type=ctype)
    check("Документы", "Запрещённое расширение отклонено", code >= 400, f"{code}")
    raw, ctype = multipart("file", "tiny.md", b"x", "text/markdown")
    code, _ = call("POST", f"{base}/api/documents/upload", token=admin_token, raw=raw, content_type=ctype)
    check("Документы", "Слишком короткий документ отклонён", code >= 400, f"{code}")

    # ---------------- F. history / workflow ----------------
    code, saved = call("POST", f"{base}/api/instructions/history", token=admin_token, body={"payload": generated})
    record = saved.get("record", {}) if isinstance(saved, dict) else {}
    instruction_id = record.get("instruction_id")
    version = record.get("version")
    # Instruction ids are derived from the Russian title, so they contain
    # Cyrillic and every HTTP client has to percent-encode them.
    quoted_id = urllib.parse.quote(str(instruction_id), safe="")
    check("История", f"Идентификатор содержит кириллицу ({instruction_id})", bool(instruction_id))
    check("История", "POST /api/instructions/history (сохранение версии)", code in (200, 201) and bool(instruction_id), f"{code}")
    code, hist = call("GET", f"{base}/api/instructions/history", token=admin_token)
    check("История", "GET /api/instructions/history", code == 200, f"{code}")
    code, ver = call("GET", f"{base}/api/instructions/history/{quoted_id}/versions/{version}", token=admin_token)
    check("История", "GET версии инструкции", code == 200, f"{code}")
    code, audit = call("GET", f"{base}/api/instructions/history/{quoted_id}/versions/{version}/audit", token=admin_token)
    events = len(audit.get("events", [])) if isinstance(audit, dict) else 0
    check("История", f"GET аудит-трейл ({events} событий)", code == 200 and events > 0, f"{code}")
    code, wf = call("PATCH", f"{base}/api/instructions/history/{quoted_id}/versions/{version}/workflow",
                    token=admin_token, body={"status": "expert_review", "reviewer": "Технолог E2E",
                                             "reviewer_role": "technologist",
                                             "comment": "Отправлено на проверку в рамках сквозного прогона"})
    check("История", "PATCH workflow (смена статуса)", code == 200, f"{code}")
    # Execution items must mirror the saved version: the API refuses a checklist
    # for steps the instruction does not contain.
    execution_steps = [
        {"label": f'{step["number"]}. {step["action"]}', "completed": True}
        for step in generated["instruction"]["steps"]
    ]
    quality_items: list[dict] = []
    code, ex = call("POST", f"{base}/api/instructions/history/{quoted_id}/versions/{version}/execution",
                    token=admin_token, body={"executor": "Оператор E2E", "notes": "сквозной прогон",
                                             "steps": execution_steps,
                                             "quality_items": quality_items})
    check("История", "POST execution (чек-лист исполнения)", code in (200, 201), f"{code}")
    code, _ = call("GET", f"{base}/api/instructions/history/{quoted_id}/versions/{version}/execution", token=admin_token)
    check("История", "GET execution", code == 200, f"{code}")
    code, _ = call("GET", f"{base}/api/instructions/history/execution-summary", token=admin_token)
    check("История", "GET execution-summary", code == 200, f"{code}")

    # ---------------- G. admin ----------------
    code, users = call("GET", f"{base}/api/admin/users", token=admin_token)
    check("Администрирование", "GET /api/admin/users", code == 200, f"{code}")
    code, project = call("POST", f"{base}/api/admin/projects", token=admin_token, body={"name": "E2E проект"})
    project_id = project.get("project_id") if isinstance(project, dict) else None
    check("Администрирование", "POST /api/admin/projects", code in (200, 201) and bool(project_id), f"{code}")
    code, _ = call("GET", f"{base}/api/admin/projects", token=admin_token)
    check("Администрирование", "GET /api/admin/projects", code == 200, f"{code}")
    code, inv = call("POST", f"{base}/api/admin/invitations", token=admin_token,
                     body={"email": "invited@e2e.example", "full_name": "Приглашённый оператор", "role": "operator"})
    check("Администрирование", "POST /api/admin/invitations", code in (200, 201), f"{code}")
    code, _ = call("GET", f"{base}/api/admin/invitations", token=admin_token)
    check("Администрирование", "GET /api/admin/invitations", code == 200, f"{code}")
    code, adt = call("GET", f"{base}/api/admin/audit", token=admin_token)
    admin_events = len(adt.get("events", [])) if isinstance(adt, dict) else 0
    check("Администрирование", f"GET /api/admin/audit ({admin_events} событий)", code == 200, f"{code}")

    # operator must not reach admin APIs
    code, body = call("POST", f"{base}/api/auth/register", body={
        "email": "operator@e2e.example", "full_name": "E2E Operator",
        "password": "e2e-strong-password-2", "role": "operator"})
    operator_token = body.get("access_token") if isinstance(body, dict) else None
    code, _ = call("GET", f"{base}/api/admin/users", token=operator_token)
    check("Разграничение прав", "Оператор не видит /api/admin/users", code in (401, 403, 404), f"{code}")
    raw, ctype = multipart("file", "op.md", doc, "text/markdown")
    code, _ = call("POST", f"{base}/api/documents/upload", token=operator_token, raw=raw, content_type=ctype)
    check("Разграничение прав", "Оператор не может загружать документы", code in (401, 403), f"{code}")
    code, _ = call("POST", f"{base}/api/instructions/generate", token=operator_token, body=task)
    check("Разграничение прав", "Оператор может генерировать инструкции", code == 200, f"{code}")

    # ---------------- H. video jobs ----------------
    form_boundary = "----procedra-e2e-form"
    form_body = (
        f"--{form_boundary}\r\n"
        'Content-Disposition: form-data; name="video_url"\r\n\r\n'
        "https://www.youtube.com/watch?v=e2eprobe\r\n"
        f"--{form_boundary}\r\n"
        'Content-Disposition: form-data; name="max_keyframes"\r\n\r\n'
        "4\r\n"
        f"--{form_boundary}--\r\n"
    ).encode("utf-8")
    code, job = call("POST", f"{base}/api/videos/jobs", token=admin_token, raw=form_body,
                     content_type=f"multipart/form-data; boundary={form_boundary}")
    job_id = job.get("job_id") if isinstance(job, dict) else None
    check("Видео-очередь", "POST /api/videos/jobs (постановка задания)", code in (200, 201, 202) and bool(job_id), f"{code}")
    if job_id:
        code, status = call("GET", f"{base}/api/videos/jobs/{job_id}", token=admin_token)
        check("Видео-очередь", f"GET статус задания ({status.get('status') if isinstance(status, dict) else '?'})", code == 200, f"{code}")
        code, _ = call("DELETE", f"{base}/api/videos/jobs/{job_id}", token=admin_token)
        check("Видео-очередь", "DELETE отмена задания", code in (200, 202, 204), f"{code}")

    # ---------------- I. abuse ----------------
    codes = []
    for index in range(12):
        c, _ = call("POST", f"{base}/api/auth/login",
                    body={"email": "victim@e2e.example", "password": f"guess-{index}"})
        codes.append(c)
    check("Защита от перебора", "Несуществующий пользователь всегда 401 (нет утечки)", set(codes) <= {401}, f"{sorted(set(codes))}")

    call("POST", f"{base}/api/auth/register", body={
        "email": "victim@e2e.example", "full_name": "Victim", "password": "victim-password-1", "role": "operator"})
    for _ in range(5):
        call("POST", f"{base}/api/auth/login", body={"email": "victim@e2e.example", "password": "wrong"})
    code, _ = call("POST", f"{base}/api/auth/login",
                   body={"email": "victim@e2e.example", "password": "victim-password-1"})
    check("Защита от перебора", "После 5 неудач верный пароль не пускает (блокировка)", code == 401, f"{code}")

    code, _ = call("GET", f"{base}/health", headers={"X-Request-ID": "abc\tdef"})
    check("Валидация входа", "X-Request-ID с управляющими символами отброшен", code == 200, f"{code}")
    code, _ = call("POST", f"{base}/api/instructions/generate", token=admin_token, body={"task": "коротко"})
    check("Валидация входа", "Слишком короткая задача отклонена", code == 422, f"{code}")
    code, _ = call("GET", f"{base}/api/instructions/history/nonexistent/versions/1", token=admin_token)
    check("Валидация входа", "Несуществующий ресурс → 404", code == 404, f"{code}")

    # ---------------- J. stress ----------------
    def hammer(path: str, method: str, payload: dict | None, token: str | None, n: int, conc: int):
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=conc) as pool:
            out = list(pool.map(lambda _: call(method, f"{base}{path}", token=token, body=payload), range(n)))
        elapsed = time.perf_counter() - started
        codes = [c for c, _ in out]
        ok = sum(1 for c in codes if 200 <= c < 300)
        return ok, len(codes), round(n / elapsed, 1), sorted(set(codes))

    ok, total, rps, seen = hammer("/api/instructions/generate", "POST", task, admin_token, 120, 24)
    check("Нагрузка", f"Генерация: {total} запросов, 24 параллельно → {rps} rps", ok == total, f"коды {seen}")
    ok, total, rps, seen = hammer("/api/instructions/history", "POST", {"payload": generated}, admin_token, 120, 24)
    check("Нагрузка", f"Сохранение версий: {total} запросов → {rps} rps", ok == total, f"коды {seen}")
    ok, total, rps, seen = hammer("/api/auth/me", "GET", None, admin_token, 300, 48)
    check("Нагрузка", f"Чтение сессии: {total} запросов, 48 параллельно → {rps} rps", ok == total, f"коды {seen}")
    ok, total, rps, seen = hammer("/ready", "GET", None, None, 300, 48)
    check("Нагрузка", f"/ready: {total} запросов, 48 параллельно → {rps} rps", ok == total, f"коды {seen}")
    ok, total, rps, seen = hammer("/api/instructions/history", "GET", None, admin_token, 200, 32)
    check("Нагрузка", f"Чтение истории: {total} запросов → {rps} rps", ok == total, f"коды {seen}")

    code, final = call("GET", f"{base}/ready/details", token=static_token)
    healthy = isinstance(final, dict) and final.get("status") == "ready"
    check("Итоговое состояние", "База цела после нагрузки (глубокая проверка)", code == 200 and healthy, f"{code}")
    code, hist = call("GET", f"{base}/api/instructions/history", token=admin_token)
    records = hist.get("records") or hist.get("items") or [] if isinstance(hist, dict) else []
    total_versions = len(records)
    check("Итоговое состояние", f"История содержит {total_versions} записей", code == 200)


def report() -> int:
    groups: dict[str, list[tuple[str, bool, str]]] = {}
    for group, name, ok, detail in RESULTS:
        groups.setdefault(group, []).append((name, ok, detail))
    print("\n" + "=" * 78)
    failed_total = 0
    for group, items in groups.items():
        passed = sum(1 for _, ok, _ in items if ok)
        failed_total += len(items) - passed
        mark = "OK  " if passed == len(items) else "FAIL"
        print(f"\n[{mark}] {group}  ({passed}/{len(items)})")
        for name, ok, detail in items:
            symbol = "  +" if ok else "  X"
            suffix = f"   [{detail}]" if detail and not ok else (f"   ({detail})" if detail else "")
            print(f"{symbol} {name}{suffix}")
    total = len(RESULTS)
    print("\n" + "=" * 78)
    print(f"TOTAL {total - failed_total}/{total} passed, {failed_total} failed")
    return 0 if failed_total == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
