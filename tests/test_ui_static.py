from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def test_tab_state_synchronizes_sidebar_without_overriding_initial_generator() -> None:
    source = _read("app/static/app.js")
    sync_start = source.index("function syncTabState()")
    sync_end = source.index("function focusableModalElements", sync_start)
    sync_body = source[sync_start:sync_end]
    startup = source[source.rindex("videoGenerateButton.disabled = true;") :]

    assert 'result.setAttribute("aria-labelledby", activeButton.id)' in sync_body
    assert "syncSidebarState(activeTab);" in sync_body
    assert 'syncTabState();\n      syncSidebarState("generator");' in startup


def test_panel_heading_uses_non_negative_letter_spacing() -> None:
    css = _read("app/static/app.css")
    rules = re.findall(r"\.panel-header h2\s*\{([^}]*)\}", css)

    assert rules
    assert any("letter-spacing: 0;" in rule for rule in rules)
    assert all("letter-spacing: -" not in rule for rule in rules)


def test_browser_session_precedes_saved_api_token_and_can_fall_back_after_401() -> None:
    source = _read("app/static/app.js")
    fetch_start = source.index("async function apiFetch(")
    fetch_end = source.index("function cookieValue", fetch_start)
    fetch_body = source[fetch_start:fetch_end]

    assert "const hasAuthenticatedUser = Boolean(currentUser);" in fetch_body
    assert 'const token = hasAuthenticatedUser ? "" : apiTokenInput.value.trim();' in fetch_body
    assert "if (token && !headers.has(\"Authorization\"))" in fetch_body
    assert "if (hasAuthenticatedUser) {\n            currentUser = null;\n            syncAuthControls();\n          }" in fetch_body
    assert 'window.prompt(t("authTokenPrompt"), apiTokenInput.value.trim())' in fetch_body
    assert "return apiFetch(url, options, false);" in fetch_body


def test_auth_ui_loads_server_capabilities_and_fails_closed() -> None:
    source = _read("app/static/app.js")

    assert 'apiFetch("/api/auth/config", {}, false)' in source
    assert "public_registration_enabled: false" in source
    assert 'registerOption.hidden = !authCapabilities.public_registration_enabled;' in source
    assert 'registerOption.disabled = !authCapabilities.public_registration_enabled;' in source
    assert "authCapabilities.allowed_registration_roles.includes(value)" in source
    assert "authPasswordInput.minLength = authCapabilities.minimum_password_length;" in source
    assert "loadAuthCapabilities();" in source


def test_hidden_auth_fields_and_sticky_navigation_have_visual_regressions_guarded() -> None:
    css = _read("app/static/app.css")

    # Matched on the rule, not on its formatting: the redesign writes it on one
    # line. What matters is that `hidden` still wins over the display values the
    # layout sets, since the script hides panels with the attribute.
    assert re.search(r"\[hidden\]\s*\{\s*display:\s*none\s*!important;?\s*\}", css)
    # Below the two-column breakpoint the shell collapses to a single column.
    assert "@media (max-width: 1180px)" in css
    assert "grid-template-columns: minmax(0, 1fr);" in css


def test_localized_file_pickers_have_visible_names_and_focus_state() -> None:
    html = _read("app/static/index.html")
    js = _read("app/static/app.js")
    css = _read("app/static/app.css")

    assert html.count('class="file-picker-input"') == 2
    assert 'id="video-file-name"' in html
    assert 'id="document-file-name"' in html
    assert 'data-i18n="chooseFile"' in html
    assert 'data-i18n="noFileSelected"' in html
    assert 'chooseFile: "Выбрать файл"' in js
    assert 'noFileSelected: "Файл не выбран"' in js
    assert "function syncSelectedFileNames()" in js
    assert ".file-picker-input:focus-visible + .file-picker-action" in css


def test_claim_provenance_and_safety_findings_are_visible_in_results() -> None:
    source = _read("app/static/app.js")

    assert 'observedFacts: "Утверждения из входных данных"' in source
    assert 'observedFacts: "Input claims"' in source
    assert 'evidenceProvenance: "Происхождение и статус утверждений"' in source
    assert 'safetyFindings: "Safety-блокеры"' in source
    assert "instruction.evidence_claims || []" in source
    assert 'claim.claim_id || "no-claim-id"' in source
    assert 'claim.source_id || "none"' in source
    assert "claim.validation_record" in source
    assert "evaluation.safety_findings || []" in source
