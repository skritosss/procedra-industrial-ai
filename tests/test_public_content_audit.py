from scripts import public_content_audit


def test_public_content_audit_detects_secret_without_echoing_it(tmp_path, monkeypatch) -> None:
    secret = "sk-proj-" + "A" * 40
    (tmp_path / "safe.txt").write_text("OPENAI_API_KEY=", encoding="utf-8")
    (tmp_path / "leak.txt").write_text(secret, encoding="utf-8")
    monkeypatch.setattr(public_content_audit, "_candidate_paths", lambda project_root: ["safe.txt", "leak.txt"])

    result = public_content_audit.audit_public_content(tmp_path)

    assert result["ok"] is False
    assert result["findings"] == [{"path": "leak.txt", "type": "openai_api_key"}]
    assert secret not in str(result)


def test_public_content_audit_skips_binary_and_accepts_clean_text(tmp_path, monkeypatch) -> None:
    (tmp_path / "binary.pdf").write_bytes(b"%PDF\0" + b"sk-proj-" + b"B" * 40)
    (tmp_path / "readme.md").write_text("No credentials here.", encoding="utf-8")
    monkeypatch.setattr(public_content_audit, "_candidate_paths", lambda project_root: ["binary.pdf", "readme.md"])

    result = public_content_audit.audit_public_content(tmp_path)

    assert result["ok"] is True
    assert result["scanned_files"] == 1
    assert result["findings"] == []


def test_public_content_audit_fails_closed_on_oversized_text(tmp_path, monkeypatch) -> None:
    (tmp_path / "large.txt").write_bytes(b"x" * 9)
    monkeypatch.setattr(public_content_audit, "MAX_TEXT_BYTES", 8)
    monkeypatch.setattr(public_content_audit, "_candidate_paths", lambda project_root: ["large.txt"])

    result = public_content_audit.audit_public_content(tmp_path)

    assert result["ok"] is False
    assert result["oversized_text_files"] == ["large.txt"]
