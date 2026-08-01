from scripts import public_scope_audit as audit


def test_public_scope_audit_allows_env_example_but_rejects_private_env() -> None:
    assert audit._is_private_path(".env.example") is False
    assert audit._is_private_path(".env.local") is True
    assert audit._is_private_path("generated/app.sqlite3") is True
    assert audit._is_private_path("docs/.DS_Store") is True
    assert audit._is_private_path("docs/research/procedra_evidence_audit.md") is True
    assert audit._is_private_path("docs/research/procedra_final_pre_submission_quality_audit.md") is True


def test_public_scope_audit_summarizes_ignored_artifacts(tmp_path) -> None:
    generated = tmp_path / "generated"
    (generated / "app.sqlite3").parent.mkdir(parents=True)
    (generated / "app.sqlite3").write_bytes(b"db")
    (generated / "keyframes" / "frame.jpg").parent.mkdir(parents=True)
    (generated / "keyframes" / "frame.jpg").write_bytes(b"jpg")

    result = audit.summarize_artifacts(generated, project_root=tmp_path, sample_limit=1)

    assert result.exists is True
    assert result.files == 2
    assert result.bytes == 5
    assert result.samples == ["generated/app.sqlite3"]


def test_public_scope_audit_suppresses_private_filename_samples_by_default(tmp_path, monkeypatch) -> None:
    (tmp_path / ".gitignore").write_text("\n".join(audit.REQUIRED_GITIGNORE_ENTRIES), encoding="utf-8")
    (tmp_path / ".dockerignore").write_text(
        "\n".join(audit.REQUIRED_DOCKERIGNORE_ENTRIES), encoding="utf-8"
    )
    generated = tmp_path / "generated"
    generated.mkdir()
    (generated / "customer-process-name.txt").write_text("private", encoding="utf-8")
    monkeypatch.setattr(audit, "IGNORED_ARTIFACT_ROOTS", (generated,))
    monkeypatch.setattr(audit, "_git_paths", lambda _root, _args: ["README.md"])
    monkeypatch.setattr(audit, "_git_add_dry_run_paths", lambda _root: ["README.md"])

    result = audit.audit_public_scope(project_root=tmp_path)

    assert result.ok is True
    assert result.ignored_artifacts[0].files == 1
    assert result.ignored_artifacts[0].samples == []


def test_public_scope_audit_fails_when_private_paths_would_be_staged(tmp_path, monkeypatch) -> None:
    (tmp_path / ".gitignore").write_text("\n".join(audit.REQUIRED_GITIGNORE_ENTRIES), encoding="utf-8")
    (tmp_path / ".dockerignore").write_text(
        "\n".join(audit.REQUIRED_DOCKERIGNORE_ENTRIES), encoding="utf-8"
    )
    monkeypatch.setattr(audit, "IGNORED_ARTIFACT_ROOTS", (tmp_path / "generated",))
    monkeypatch.setattr(audit, "_git_paths", lambda _root, _args: ["README.md"])
    monkeypatch.setattr(audit, "_git_add_dry_run_paths", lambda _root: ["reports/private.md"])

    result = audit.audit_public_scope(project_root=tmp_path)

    assert result.ok is False
    assert result.dry_run_private_paths == ["reports/private.md"]


def test_public_scope_audit_passes_with_expected_public_paths(tmp_path, monkeypatch) -> None:
    (tmp_path / ".gitignore").write_text("\n".join(audit.REQUIRED_GITIGNORE_ENTRIES), encoding="utf-8")
    (tmp_path / ".dockerignore").write_text(
        "\n".join(audit.REQUIRED_DOCKERIGNORE_ENTRIES), encoding="utf-8"
    )
    monkeypatch.setattr(audit, "IGNORED_ARTIFACT_ROOTS", (tmp_path / "generated",))
    monkeypatch.setattr(audit, "_git_paths", lambda _root, _args: ["README.md", ".env.example"])
    monkeypatch.setattr(audit, "_git_add_dry_run_paths", lambda _root: ["README.md", "scripts/public_scope_audit.py"])

    result = audit.audit_public_scope(project_root=tmp_path)

    assert result.ok is True
    assert result.gitignore_missing_entries == []
    assert result.tracked_private_paths == []
    assert result.dry_run_private_paths == []


def test_public_scope_audit_reports_missing_gitignore_entries(tmp_path, monkeypatch) -> None:
    (tmp_path / ".gitignore").write_text("generated/\n", encoding="utf-8")
    monkeypatch.setattr(audit, "IGNORED_ARTIFACT_ROOTS", ())
    monkeypatch.setattr(audit, "_git_paths", lambda _root, _args: [])
    monkeypatch.setattr(audit, "_git_add_dry_run_paths", lambda _root: [])

    result = audit.audit_public_scope(project_root=tmp_path)

    assert result.ok is False
    assert "reports/" in result.gitignore_missing_entries


def test_public_scope_audit_reports_missing_dockerignore_entries(tmp_path, monkeypatch) -> None:
    (tmp_path / ".gitignore").write_text("\n".join(audit.REQUIRED_GITIGNORE_ENTRIES), encoding="utf-8")
    (tmp_path / ".dockerignore").write_text("generated/\n", encoding="utf-8")
    monkeypatch.setattr(audit, "IGNORED_ARTIFACT_ROOTS", ())
    monkeypatch.setattr(audit, "_git_paths", lambda _root, _args: [])
    monkeypatch.setattr(audit, "_git_add_dry_run_paths", lambda _root: [])

    result = audit.audit_public_scope(project_root=tmp_path)

    assert result.ok is False
    assert "docs/research/" in result.dockerignore_missing_entries
    assert result.gitignore_missing_entries == []
