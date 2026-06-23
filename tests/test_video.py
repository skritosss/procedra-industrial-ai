from pathlib import Path
import urllib.request

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import videos
from pydantic import ValidationError

from app.schemas.video import FrameAnalysis, Keyframe, VideoKeyframeResponse, VideoSegment
from app.core.settings import get_settings
from app.core.authorization import create_project, get_resource_ownership, register_resource_ownership
from app.storage.auth_store import create_organization, create_session, create_user
from app.vision import keyframes
from app.vision import frame_analysis
from app.vision.frame_analysis import (
    analyze_keyframes,
    build_frame_analysis_context,
    build_video_segment_context,
    build_video_segments,
)
from app.vision.keyframes import download_video_from_url, extract_keyframes, save_uploaded_video
from app.vision.safe_egress import (
    EgressPolicyError,
    ResolvedTarget,
    VideoEgressPolicy,
    _PinnedHTTPConnection,
    _PinnedHTTPHandler,
    _ValidatedRedirectHandler,
)


def test_keyframe_route_isolated_between_projects(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "auth.sqlite3"
    keyframe_root = tmp_path / "keyframes"
    settings = get_settings().model_copy(
        update={"deployment_mode": "production", "database_path": database_path}
    )
    monkeypatch.setattr("app.main.KEYFRAMES_DIR", keyframe_root)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    organization_id = create_organization("Project Video", database_path=database_path)
    owner = create_user(
        "video-project@example.com",
        "Video Project Owner",
        "strong-password-1",
        organization_id=organization_id,
        database_path=database_path,
    )
    project_id = create_project(
        organization_id,
        "Restricted Video",
        owner.user_id,
        database_path=database_path,
    )
    video_id = "c" * 32
    frame_dir = keyframe_root / organization_id / video_id
    frame_dir.mkdir(parents=True)
    (frame_dir / "frame_01.jpg").write_bytes(b"frame")
    register_resource_ownership(
        organization_id,
        project_id,
        "video",
        video_id,
        owner.user_id,
        database_path=database_path,
    )
    token = create_session(owner.user_id, database_path=database_path)
    endpoint = f"/generated/keyframes/{organization_id}/{video_id}/frame_01.jpg"
    client = TestClient(app)

    assert client.get(
        endpoint,
        headers={"Authorization": f"Bearer {token}", "X-Project-ID": project_id},
    ).status_code == 200
    assert client.get(endpoint, headers={"Authorization": f"Bearer {token}"}).status_code == 404


def test_production_keyframe_get_does_not_claim_unowned_file(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "auth.sqlite3"
    keyframe_root = tmp_path / "keyframes"
    settings = get_settings().model_copy(
        update={"deployment_mode": "production", "database_path": database_path}
    )
    monkeypatch.setattr("app.main.KEYFRAMES_DIR", keyframe_root)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    organization_id = create_organization("Unowned Video", database_path=database_path)
    user = create_user(
        "unowned-video@example.com",
        "Unowned Video User",
        "strong-password-1",
        organization_id=organization_id,
        database_path=database_path,
    )
    token = create_session(user.user_id, database_path=database_path)
    video_id = "e" * 32
    frame_dir = keyframe_root / organization_id / video_id
    frame_dir.mkdir(parents=True)
    (frame_dir / "frame_01.jpg").write_bytes(b"frame")
    endpoint = f"/generated/keyframes/{organization_id}/{video_id}/frame_01.jpg"

    response = TestClient(app).get(
        endpoint,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert get_resource_ownership(
        organization_id,
        "video",
        video_id,
        database_path=database_path,
    ) is None


def _make_test_video(path: Path, frame_count: int = 12) -> None:
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        6.0,
        (96, 64),
    )
    for index in range(frame_count):
        frame = np.zeros((64, 96, 3), dtype=np.uint8)
        frame[:, :, 0] = min(index * 20, 255)
        frame[:, :, 1] = 60
        cv2.putText(frame, str(index), (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        writer.write(frame)
    writer.release()


def _make_scene_change_video(path: Path) -> None:
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        6.0,
        (96, 64),
    )
    for index in range(18):
        frame = np.zeros((64, 96, 3), dtype=np.uint8)
        if index < 6:
            frame[:, :] = (20, 20, 20)
        elif index < 12:
            frame[:, :] = (120, 120, 120)
            cv2.rectangle(frame, (10, 10), (80, 50), (255, 255, 255), 2)
        else:
            frame[:, :] = (40, 120, 200)
            cv2.circle(frame, (48, 32), 20, (255, 255, 255), 2)
        writer.write(frame)
    writer.release()


def _make_uniform_video(path: Path, frame_count: int = 12) -> None:
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        6.0,
        (96, 64),
    )
    for _ in range(frame_count):
        frame = np.full((64, 96, 3), 80, dtype=np.uint8)
        writer.write(frame)
    writer.release()


def test_extract_keyframes_from_synthetic_video(tmp_path) -> None:
    video_path = tmp_path / "sample.mp4"
    _make_test_video(video_path)

    video_id, saved_path = save_uploaded_video("sample.mp4", video_path.read_bytes())
    response = extract_keyframes(video_id, saved_path, "sample.mp4", max_keyframes=4)

    assert response.frame_count > 0
    assert response.keyframes
    assert len(response.keyframes) <= 4
    assert all(keyframe.image_url.startswith("/generated/keyframes/") for keyframe in response.keyframes)
    assert all(keyframe.selection_score >= 0 for keyframe in response.keyframes)
    assert all(keyframe.selection_reason for keyframe in response.keyframes)


def test_extract_keyframes_prefers_high_value_scene_changes(tmp_path) -> None:
    video_path = tmp_path / "scene-change.mp4"
    _make_scene_change_video(video_path)

    video_id, saved_path = save_uploaded_video("scene-change.mp4", video_path.read_bytes())
    response = extract_keyframes(video_id, saved_path, "scene-change.mp4", max_keyframes=3)

    assert len(response.keyframes) == 3
    assert response.keyframes == sorted(response.keyframes, key=lambda item: item.frame_index)
    assert max(keyframe.selection_score for keyframe in response.keyframes) > 0
    assert any("смена сцены" in keyframe.selection_reason for keyframe in response.keyframes)


def test_extract_keyframes_skips_visual_duplicates_in_uniform_video(tmp_path) -> None:
    video_path = tmp_path / "uniform.mp4"
    _make_uniform_video(video_path)

    video_id, saved_path = save_uploaded_video("uniform.mp4", video_path.read_bytes())
    response = extract_keyframes(video_id, saved_path, "uniform.mp4", max_keyframes=4)

    assert len(response.keyframes) == 1
    assert any("меньше кадров" in note for note in response.notes)


def test_high_value_selection_preserves_temporal_coverage() -> None:
    candidates = []
    for index in range(9):
        frame = np.full((8, 8, 3), index * 20, dtype=np.uint8)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        candidates.append(
            keyframes.KeyframeCandidate(
                frame_index=index,
                frame=frame,
                gray=gray,
                timestamp_seconds=float(index),
                scene_change=float(index),
                sharpness=100.0,
                brightness_score=0.8,
                contrast_score=0.5,
                score=1.0 if index in {1, 4, 7} else 0.1,
            )
        )

    selected = keyframes._select_high_value_candidates(candidates, 3)

    assert [candidate.frame_index for candidate in selected] == [1, 4, 7]


def test_extract_keyframes_reports_failed_image_writes(monkeypatch, tmp_path) -> None:
    video_path = tmp_path / "sample.mp4"
    _make_test_video(video_path)
    video_id, saved_path = save_uploaded_video("sample.mp4", video_path.read_bytes())
    monkeypatch.setattr(cv2, "imwrite", lambda *args, **kwargs: False)

    response = extract_keyframes(video_id, saved_path, "sample.mp4", max_keyframes=2)

    assert not response.keyframes
    assert any("сохранить" in note for note in response.notes)


def test_keyframe_selection_score_rejects_values_above_one() -> None:
    with pytest.raises(ValidationError):
        Keyframe(
            frame_index=1,
            timestamp_seconds=1,
            image_path="generated/keyframes/a.jpg",
            image_url="/generated/keyframes/a.jpg",
            selection_score=1.2,
        )


def test_video_keyframes_endpoint_accepts_upload(tmp_path) -> None:
    video_path = tmp_path / "sample.mp4"
    _make_test_video(video_path)
    client = TestClient(app)

    with video_path.open("rb") as file:
        response = client.post(
            "/api/videos/keyframes",
            data={"max_keyframes": "4"},
            files={"file": ("sample.mp4", file, "video/mp4")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["keyframes"]
    assert payload["frame_analyses"]
    assert payload["video_segments"]
    assert payload["duration_seconds"] > 0
    assert payload["visual_quality"] == "uploaded"
    assert any("Анализ ключевых кадров" in note for note in payload["notes"])
    assert any("смысловые этапы" in note.lower() for note in payload["notes"])


def test_video_keyframes_endpoint_rejects_unsupported_file() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/videos/keyframes",
        data={"max_keyframes": "4"},
        files={"file": ("sample.txt", b"not a video", "text/plain")},
    )

    assert response.status_code == 400


def test_production_keyframes_are_isolated_by_organization(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "auth.sqlite3"
    keyframe_root = tmp_path / "keyframes"
    video_root = tmp_path / "videos"
    bootstrap_token = "video-isolation-bootstrap-token-32-plus"
    settings = get_settings().model_copy(
        update={
            "deployment_mode": "production",
            "api_access_token": bootstrap_token,
            "auth_public_registration_enabled": False,
            "auth_allow_role_self_assignment": False,
            "auth_min_password_length": 12,
            "database_path": database_path,
        }
    )
    monkeypatch.setattr("app.main.KEYFRAMES_DIR", keyframe_root)
    monkeypatch.setattr("app.vision.keyframes.PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("app.vision.keyframes.KEYFRAME_DIR", keyframe_root)
    monkeypatch.setattr("app.vision.keyframes.UPLOAD_DIR", video_root)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.videos.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    organization_a = create_organization("Video A", database_path=database_path)
    organization_b = create_organization("Video B", database_path=database_path)
    user_a = create_user(
        "video-a@example.com",
        "Video A",
        "strong-production-password-a",
        organization_id=organization_a,
        database_path=database_path,
    )
    user_b = create_user(
        "video-b@example.com",
        "Video B",
        "strong-production-password-b",
        organization_id=organization_b,
        database_path=database_path,
    )
    headers_a = {"Authorization": f"Bearer {create_session(user_a.user_id, database_path=database_path)}"}
    headers_b = {"Authorization": f"Bearer {create_session(user_b.user_id, database_path=database_path)}"}
    client = TestClient(app)
    static_upload = client.post(
        "/api/videos/keyframes",
        headers={"Authorization": f"Bearer {bootstrap_token}"},
        data={"max_keyframes": "1"},
        files={"file": ("sample.mp4", b"not processed", "video/mp4")},
    )
    assert static_upload.status_code == 401

    video_path = tmp_path / "organization-a.mp4"
    _make_test_video(video_path)
    with video_path.open("rb") as file:
        uploaded = client.post(
            "/api/videos/keyframes",
            headers=headers_a,
            data={"max_keyframes": "2"},
            files={"file": ("organization-a.mp4", file, "video/mp4")},
        )

    assert uploaded.status_code == 200, uploaded.text
    payload = uploaded.json()
    video_id = payload["video_id"]
    assert any((video_root / organization_a).glob(f"{video_id}.*"))
    assert not (video_root / organization_b).exists()
    assert (keyframe_root / organization_a / video_id / "frame_01.jpg").is_file()
    assert not (keyframe_root / organization_b / video_id).exists()
    endpoint = payload["keyframes"][0]["image_url"]
    assert endpoint.startswith(f"/generated/keyframes/{organization_a}/{video_id}/")
    assert client.get(endpoint, headers=headers_a).status_code == 200
    own_frame = client.get(endpoint, headers=headers_a)
    assert own_frame.headers["Cache-Control"] == "private, no-store"
    assert own_frame.headers["Vary"] == "Authorization, X-Project-ID"
    assert client.get(endpoint, headers=headers_b).status_code == 404
    assert client.get(endpoint, headers={"Authorization": f"Bearer {bootstrap_token}"}).status_code == 401
    legacy_endpoint = endpoint.replace(f"/{organization_a}/{video_id}/", f"/{video_id}/")
    assert client.get(legacy_endpoint, headers=headers_a).status_code == 404


def test_demo_tenant_keyframe_requires_matching_user_session(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "auth.sqlite3"
    keyframe_root = tmp_path / "keyframes"
    settings = get_settings().model_copy(update={"deployment_mode": "demo", "database_path": database_path})
    monkeypatch.setattr("app.main.KEYFRAMES_DIR", keyframe_root)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    organization_id = create_organization("Demo Tenant", database_path=database_path)
    user = create_user(
        "demo-tenant@example.com",
        "Demo Tenant User",
        "strong-password-1",
        organization_id=organization_id,
        database_path=database_path,
    )
    token = create_session(user.user_id, database_path=database_path)
    video_id = "b" * 32
    frame_dir = keyframe_root / organization_id / video_id
    frame_dir.mkdir(parents=True)
    (frame_dir / "frame_01.jpg").write_bytes(b"frame")
    register_resource_ownership(
        organization_id,
        organization_id,
        "video",
        video_id,
        user.user_id,
        database_path=database_path,
    )
    endpoint = f"/generated/keyframes/{organization_id}/{video_id}/frame_01.jpg"
    client = TestClient(app)

    assert client.get(endpoint).status_code == 401
    assert client.get(endpoint, headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_video_keyframes_endpoint_rejects_oversized_upload_before_processing(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.videos.get_settings",
        lambda: type("Settings", (), {"video_max_bytes": 4})(),
    )
    client = TestClient(app)

    response = client.post(
        "/api/videos/keyframes",
        data={"max_keyframes": "4"},
        files={"file": ("sample.mp4", b"12345", "video/mp4")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"
    assert "too large" in response.json()["error"]["message"]


def test_read_upload_limited_rejects_unknown_size_stream() -> None:
    class FakeUpload:
        def __init__(self):
            self._chunks = [b"123", b"45"]

        async def read(self, size: int = -1):
            return self._chunks.pop(0) if self._chunks else b""

    with pytest.raises(ValueError, match="too large"):
        import anyio

        anyio.run(videos._read_upload_limited, FakeUpload(), 4)


def test_video_keyframes_from_url_endpoint_uses_downloader(monkeypatch, tmp_path) -> None:
    video_path = tmp_path / "sample.mp4"
    _make_test_video(video_path)
    captured = {}

    def fake_download(
        video_url: str,
        visual_quality: str = "720",
        organization_id: str = "legacy",
    ):
        captured["video_url"] = video_url
        captured["visual_quality"] = visual_quality
        captured["organization_id"] = organization_id
        video_id, saved_path = save_uploaded_video("sample.mp4", video_path.read_bytes())
        return video_id, saved_path, {
            "title": "Downloaded sample",
            "source_url": video_url,
            "extracted_context": "Название видео: Downloaded sample\n\nРаспознанная речь: подготовить станок к работе.",
            "transcript": "подготовить станок к работе",
            "visual_quality": f"{visual_quality}p",
        }

    monkeypatch.setattr(videos, "download_video_from_url", fake_download)
    client = TestClient(app)

    response = client.post(
        "/api/videos/keyframes-from-url",
        data={"video_url": "https://example.com/video", "max_keyframes": "4", "visual_quality": "720"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["original_filename"] == "Downloaded sample"
    assert payload["source_url"] == "https://example.com/video"
    assert payload["visual_quality"] == "720p"
    assert "подготовить станок" in payload["extracted_context"]
    assert payload["transcript"]
    assert payload["keyframes"]
    assert payload["frame_analyses"]
    assert payload["video_segments"]
    assert "Анализ ключевых кадров" in payload["extracted_context"]
    assert "Смысловые этапы видео" in payload["extracted_context"]
    assert any("ссылке" in note for note in payload["notes"])
    assert any("720p" in note for note in payload["notes"])
    assert any("субтитр" in note.lower() for note in payload["notes"])
    assert captured == {
        "video_url": "https://example.com/video",
        "visual_quality": "720",
        "organization_id": "legacy",
    }


def test_video_url_allowlist_rejects_unapproved_public_host(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.vision.keyframes.get_settings",
        lambda: type(
            "Settings",
            (),
                {
                    "video_allowed_hosts": ("youtube.com", "youtu.be"),
                    "video_network_timeout_seconds": 15,
                },
        )(),
    )

    with pytest.raises(ValueError, match="not allowed"):
        keyframes._validate_public_video_url("https://example.com/video")


def test_video_url_allowlist_accepts_allowed_subdomain(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.vision.keyframes.get_settings",
        lambda: type(
            "Settings",
            (),
                {
                    "video_allowed_hosts": ("youtube.com",),
                    "video_network_timeout_seconds": 15,
                },
        )(),
    )
    monkeypatch.setattr(keyframes.socket, "getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("8.8.8.8", 0))])

    keyframes._validate_public_video_url("https://www.youtube.com/watch?v=test")


def test_video_keyframes_from_url_rejects_blank_url() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/videos/keyframes-from-url",
        data={"video_url": " ", "max_keyframes": "4"},
    )

    assert response.status_code == 400


def test_video_keyframes_from_url_rejects_invalid_keyframe_count_before_download(monkeypatch) -> None:
    called = False

    def fake_download(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("download should not be called")

    monkeypatch.setattr(videos, "download_video_from_url", fake_download)
    client = TestClient(app)

    response = client.post(
        "/api/videos/keyframes-from-url",
        data={"video_url": "https://example.com/video", "max_keyframes": "999"},
    )

    assert response.status_code == 400
    assert "max_keyframes" in response.json()["error"]["message"]
    assert called is False


def test_video_keyframes_upload_rejects_invalid_keyframe_count_before_reading_file(monkeypatch) -> None:
    called = False

    def fake_save(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("upload should not be saved")

    monkeypatch.setattr(videos, "save_uploaded_video", fake_save)
    client = TestClient(app)

    response = client.post(
        "/api/videos/keyframes",
        data={"max_keyframes": "0"},
        files={"file": ("sample.mp4", b"not-read", "video/mp4")},
    )

    assert response.status_code == 400
    assert "max_keyframes" in response.json()["error"]["message"]
    assert called is False


def test_download_video_from_url_rejects_non_http_urls() -> None:
    with pytest.raises(ValueError, match="http:// or https://"):
        download_video_from_url("file:///private/video.mp4")


def test_download_video_from_url_rejects_private_hosts() -> None:
    with pytest.raises(ValueError, match="public host"):
        download_video_from_url("http://127.0.0.1/video.mp4")


def test_download_video_from_url_rejects_invalid_visual_quality() -> None:
    with pytest.raises(ValueError, match="visual_quality"):
        download_video_from_url("https://example.com/video", "999")


def test_known_oversized_remote_video_is_rejected_before_visual_download(monkeypatch) -> None:
    monkeypatch.setattr(
        keyframes,
        "get_settings",
        lambda: type("Settings", (), {"video_max_bytes": 4, "video_max_duration_seconds": 1800})(),
    )

    with pytest.raises(ValueError, match="too large"):
        keyframes._reject_known_oversized_video({"filesize": 5})


def test_known_oversized_remote_format_is_rejected_before_visual_download(monkeypatch) -> None:
    monkeypatch.setattr(
        keyframes,
        "get_settings",
        lambda: type("Settings", (), {"video_max_bytes": 4, "video_max_duration_seconds": 1800})(),
    )

    with pytest.raises(ValueError, match="too large"):
        keyframes._reject_known_oversized_video({"formats": [{"filesize_approx": 5}]})


def test_known_overlong_remote_video_is_rejected_before_visual_download(monkeypatch) -> None:
    monkeypatch.setattr(
        keyframes,
        "get_settings",
        lambda: type("Settings", (), {"video_max_bytes": 1024, "video_max_duration_seconds": 60})(),
    )

    with pytest.raises(ValueError, match="too long"):
        keyframes._reject_known_oversized_video({"duration": 61})


def test_remove_download_candidates_deletes_partial_and_finished_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(keyframes, "UPLOAD_DIR", tmp_path)
    video_id = "video123"
    partial = tmp_path / f"{video_id}.mp4.part"
    finished = tmp_path / f"{video_id}.mp4"
    unrelated = tmp_path / "other.mp4"
    partial.write_bytes(b"partial")
    finished.write_bytes(b"finished")
    unrelated.write_bytes(b"other")

    keyframes._remove_download_candidates(video_id)

    assert not partial.exists()
    assert not finished.exists()
    assert unrelated.exists()


def test_video_response_rejects_unbounded_text_payloads() -> None:
    with pytest.raises(ValidationError):
        VideoKeyframeResponse(
            video_id="v",
            original_filename="sample.mp4",
            frame_count=1,
            fps=1,
            duration_seconds=1,
            extracted_context="x" * 12001,
        )


def test_video_context_explains_missing_description_and_transcript() -> None:
    context = keyframes._build_extracted_context(
        {
            "title": "Подготовка оборудования",
            "source_url": "https://example.com/video",
            "description": "",
            "transcript": "",
        }
    )

    assert "Описание видео не найдено" in context
    assert "Субтитры или распознанная речь не найдены" in context
    assert "ключевые кадры" in context


def test_visual_quality_format_does_not_fall_back_above_requested_quality() -> None:
    format_selector = keyframes._format_for_visual_quality(360)

    assert "height<=360" in format_selector
    assert not format_selector.endswith("/best")


def test_find_downloaded_video_ignores_partial_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(keyframes, "UPLOAD_DIR", tmp_path)
    video_id = "video123"
    (tmp_path / f"{video_id}.mp4.part").write_bytes(b"partial")

    assert keyframes._find_downloaded_video(video_id) is None


def test_find_downloaded_video_returns_supported_finished_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(keyframes, "UPLOAD_DIR", tmp_path)
    video_id = "video123"
    finished = tmp_path / f"{video_id}.mp4"
    finished.write_bytes(b"complete")
    (tmp_path / f"{video_id}.mp4.part").write_bytes(b"partial")

    assert keyframes._find_downloaded_video(video_id) == finished


def test_extract_transcript_prefers_manual_subtitles(monkeypatch) -> None:
    def fake_extract(tracks, **kwargs):
        return tracks[0]["text"] if tracks else ""

    monkeypatch.setattr(keyframes, "_extract_transcript_from_tracks", fake_extract)
    info = {
        "subtitles": {"ru": [{"text": "manual subtitles"}]},
        "automatic_captions": {"ru": [{"text": "automatic captions"}]},
    }

    assert keyframes._extract_transcript(info) == "manual subtitles"


def test_extract_transcript_rejects_private_subtitle_url(monkeypatch) -> None:
    called = False

    def fake_open(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("private subtitle URL should not be fetched")

    policy = VideoEgressPolicy(("example.com",), 15)
    monkeypatch.setattr(policy, "open", fake_open)

    transcript = keyframes._extract_transcript_from_tracks(
        [{"ext": "json3", "url": "http://127.0.0.1/subtitles.json"}],
        policy=policy,
    )

    assert transcript == ""
    assert called is False


def test_extract_transcript_rejects_oversized_subtitle_track(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self, size):
            return b"x" * (keyframes.TRANSCRIPT_TRACK_MAX_BYTES + 1)

    policy = VideoEgressPolicy(
        ("example.com",),
        15,
        resolver=lambda *args, **kwargs: [(None, None, None, None, ("8.8.8.8", 0))],
    )
    monkeypatch.setattr(policy, "open", lambda *args, **kwargs: FakeResponse())

    transcript = keyframes._extract_transcript_from_tracks(
        [{"ext": "json3", "url": "https://example.com/subtitles.json"}],
        policy=policy,
    )

    assert transcript == ""


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/video",
        "http://10.0.0.1/video",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/video",
        "http://[fe80::1]/video",
        "http://[fc00::1]/video",
    ],
)
def test_video_egress_rejects_non_public_ipv4_and_ipv6(url: str) -> None:
    with pytest.raises(EgressPolicyError, match="public host"):
        VideoEgressPolicy((), 15).resolve(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://%31%32%37.0.0.1/video",
        "http://example.com%2f@127.0.0.1/video",
        "http://example.com\\@127.0.0.1/video",
        "http://user:password@example.com/video",
        "http://[fe80::1%25eth0]/video",
    ],
)
def test_video_egress_rejects_encoded_or_ambiguous_authorities(url: str) -> None:
    with pytest.raises(EgressPolicyError):
        VideoEgressPolicy(("example.com",), 15).resolve(url)


def test_video_egress_rejects_mixed_public_and_private_dns_answers() -> None:
    policy = VideoEgressPolicy(
        ("example.com",),
        15,
        resolver=lambda *args, **kwargs: [
            (None, None, None, None, ("8.8.8.8", 443)),
            (None, None, None, None, ("127.0.0.1", 443)),
        ],
    )

    with pytest.raises(EgressPolicyError, match="public host"):
        policy.resolve("https://example.com/video")


def test_redirect_chain_is_revalidated_against_allowlist_and_public_dns() -> None:
    answers = {
        "video.example.com": "8.8.8.8",
        "cdn.example.com": "1.1.1.1",
        "metadata.example.com": "169.254.169.254",
    }
    policy = VideoEgressPolicy(
        ("example.com",),
        15,
        resolver=lambda host, *args, **kwargs: [(None, None, None, None, (answers[host], 443))],
    )
    handler = _ValidatedRedirectHandler(policy)
    first = urllib.request.Request("https://video.example.com/start")

    second = handler.redirect_request(first, None, 302, "Found", {}, "https://cdn.example.com/media")

    assert second is not None
    with pytest.raises(EgressPolicyError, match="public host"):
        handler.redirect_request(second, None, 302, "Found", {}, "https://metadata.example.com/token")
    with pytest.raises(EgressPolicyError, match="not allowed"):
        handler.redirect_request(second, None, 302, "Found", {}, "https://attacker.invalid/video")


def test_cross_origin_redirect_drops_sensitive_headers() -> None:
    policy = VideoEgressPolicy(
        ("example.com",),
        15,
        resolver=lambda *args, **kwargs: [(None, None, None, None, ("8.8.8.8", 443))],
    )
    request = urllib.request.Request(
        "https://video.example.com/start",
        headers={"Authorization": "Bearer secret", "Cookie": "session=secret"},
    )

    redirected = _ValidatedRedirectHandler(policy).redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        "https://cdn.example.com/media",
    )

    assert redirected is not None
    assert redirected.get_header("Authorization") is None
    assert redirected.get_header("Cookie") is None


def test_dns_rebinding_is_rechecked_before_connection() -> None:
    answers = iter(["8.8.8.8", "127.0.0.1"])
    policy = VideoEgressPolicy(
        ("example.com",),
        15,
        resolver=lambda *args, **kwargs: [(None, None, None, None, (next(answers), 443))],
    )
    request = urllib.request.Request("https://example.com/video")

    policy.resolve(request.full_url)
    with pytest.raises(EgressPolicyError, match="public host"):
        _PinnedHTTPHandler(policy).http_open(request)


def test_validated_connection_uses_pinned_ip_not_hostname(monkeypatch) -> None:
    connected_to: list[tuple[str, int]] = []

    class FakeSocket:
        pass

    def fake_create_connection(address, **kwargs):
        connected_to.append(address)
        return FakeSocket()

    monkeypatch.setattr("app.vision.safe_egress.socket.create_connection", fake_create_connection)
    target = ResolvedTarget(
        url="http://video.example.com/media",
        hostname="video.example.com",
        port=80,
        addresses=("8.8.8.8",),
    )

    connection = _PinnedHTTPConnection("video.example.com", target=target, timeout=5)
    connection.connect()

    assert connected_to == [("8.8.8.8", 80)]


def test_download_info_rejects_external_transport_before_download() -> None:
    policy = VideoEgressPolicy(
        ("example.com",),
        15,
        resolver=lambda *args, **kwargs: [(None, None, None, None, ("8.8.8.8", 443))],
    )

    with pytest.raises(ValueError, match="external transport"):
        keyframes._validate_download_info_egress(
            {"url": "rtmp://example.com/live", "protocol": "rtmp"},
            policy,
        )


def test_download_info_validates_manifest_and_fragment_hosts() -> None:
    policy = VideoEgressPolicy(
        ("video.example.com",),
        15,
        resolver=lambda *args, **kwargs: [(None, None, None, None, ("8.8.8.8", 443))],
    )

    with pytest.raises(EgressPolicyError, match="not allowed"):
        keyframes._validate_download_info_egress(
            {
                "url": "https://video.example.com/playlist.m3u8",
                "manifest_url": "https://video.example.com/playlist.m3u8",
                "protocol": "m3u8_native",
                "fragments": [{"url": "https://cdn.example.net/segment-1.ts"}],
            },
            policy,
        )


def test_subtitle_fetch_uses_same_host_allowlist_before_open(monkeypatch) -> None:
    called = False
    policy = VideoEgressPolicy(
        ("video.example.com",),
        15,
        resolver=lambda *args, **kwargs: [(None, None, None, None, ("8.8.8.8", 443))],
    )

    def fake_open(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("disallowed subtitle host must not be opened")

    monkeypatch.setattr(policy, "open", fake_open)

    transcript = keyframes._extract_transcript_from_tracks(
        [{"ext": "json3", "url": "https://captions.example.net/subtitles.json"}],
        policy=policy,
    )

    assert transcript == ""
    assert called is False


def test_frame_analysis_cleans_empty_list_values() -> None:
    analysis = FrameAnalysis(
        frame_index=1,
        timestamp_seconds=0,
        summary="Кадр",
        visible_equipment=[" Станок ", "", " "],
    )

    assert analysis.visible_equipment == ["Станок"]


def test_video_segment_rejects_invalid_time_range() -> None:
    with pytest.raises(ValidationError):
        VideoSegment(
            segment_index=1,
            start_seconds=10,
            end_seconds=5,
            frame_indices=[1],
            summary="Некорректный этап",
        )


def test_analyze_keyframes_falls_back_when_openai_disabled(monkeypatch, tmp_path) -> None:
    image_path = tmp_path / "frame.jpg"
    image_path.write_bytes(b"fake-image")
    monkeypatch.setattr(
        "app.vision.frame_analysis.get_settings",
        lambda: type("Settings", (), {"openai_enabled": False, "openai_api_key": None})(),
    )
    keyframe = keyframes.Keyframe(
        frame_index=10,
        timestamp_seconds=1.5,
        image_path=str(image_path),
        image_url="/generated/test/frame.jpg",
    )

    analyses = analyze_keyframes([keyframe])

    assert analyses[0].analysis_mode == "openai_disabled"
    assert analyses[0].operator_actions


def test_build_frame_analysis_context_includes_safety_details(monkeypatch, tmp_path) -> None:
    image_path = tmp_path / "frame.jpg"
    image_path.write_bytes(b"fake-image")
    monkeypatch.setattr(
        "app.vision.frame_analysis.get_settings",
        lambda: type("Settings", (), {"openai_enabled": False, "openai_api_key": None})(),
    )
    keyframe = keyframes.Keyframe(
        frame_index=10,
        timestamp_seconds=1.5,
        image_path=str(image_path),
        image_url="/generated/test/frame.jpg",
    )

    context = build_frame_analysis_context(analyze_keyframes([keyframe]))

    assert "Анализ ключевых кадров" in context
    assert "Потенциальные опасности" in context


def test_build_video_segments_groups_keyframes_into_stages() -> None:
    keyframe_items = [
        keyframes.Keyframe(frame_index=1, timestamp_seconds=1, image_path="a.jpg", image_url="/generated/keyframes/test/a.jpg"),
        keyframes.Keyframe(frame_index=10, timestamp_seconds=18, image_path="b.jpg", image_url="/generated/keyframes/test/b.jpg"),
        keyframes.Keyframe(frame_index=20, timestamp_seconds=42, image_path="c.jpg", image_url="/generated/keyframes/test/c.jpg"),
    ]
    analyses = [
        FrameAnalysis(
            frame_index=1,
            timestamp_seconds=1,
            summary="Оператор осматривает рабочее место.",
            operator_actions=["осмотр рабочей зоны"],
            visible_equipment=["рабочее место"],
            safety_observations=["опасная зона свободна"],
        ),
        FrameAnalysis(
            frame_index=10,
            timestamp_seconds=18,
            summary="Оператор проверяет защитное ограждение.",
            operator_actions=["проверка ограждения"],
            visible_equipment=["защитное ограждение"],
            potential_hazards=["риск доступа к движущимся частям"],
        ),
        FrameAnalysis(
            frame_index=20,
            timestamp_seconds=42,
            summary="Оператор фиксирует результат проверки.",
            operator_actions=["запись результата"],
            visible_equipment=["журнал смены"],
            uncertainties=["не видно подпись ответственного"],
        ),
    ]

    segments = build_video_segments(keyframe_items, analyses, duration_seconds=60, max_segments=3)
    context = build_video_segment_context(segments)

    assert len(segments) == 3
    assert segments[0].segment_index == 1
    assert segments[1].dominant_actions
    assert "Смысловые этапы видео" in context
    assert "Этап 1" in context


def test_image_data_url_rejects_paths_outside_generated(tmp_path) -> None:
    image_path = tmp_path / "frame.jpg"
    image_path.write_bytes(b"fake-image")

    with pytest.raises(ValueError, match="generated"):
        frame_analysis._image_data_url(image_path, 1024)


def test_analyze_keyframes_respects_openai_frame_limit(monkeypatch, tmp_path) -> None:
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir()
    image_path = generated_dir / "frame.jpg"
    image_path.write_bytes(b"fake-image")
    monkeypatch.setattr(frame_analysis, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(frame_analysis, "GENERATED_DIR", generated_dir)
    monkeypatch.setattr(
        frame_analysis,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "openai_enabled": True,
                "openai_api_key": "test",
                "openai_timeout_seconds": 1,
                "openai_vision_model": "test-model",
                "vision_max_keyframes": 1,
                "vision_max_image_bytes": 1024,
            },
        )(),
    )
    monkeypatch.setattr(
        frame_analysis,
        "_analyze_keyframe_with_openai",
        lambda client, model, keyframe, max_image_bytes: FrameAnalysis(
            frame_index=keyframe.frame_index,
            timestamp_seconds=keyframe.timestamp_seconds,
            summary="openai",
            analysis_mode="openai",
        ),
    )
    keyframe_items = [
        keyframes.Keyframe(frame_index=1, timestamp_seconds=1, image_path="generated/frame.jpg", image_url="/generated/frame.jpg"),
        keyframes.Keyframe(frame_index=2, timestamp_seconds=2, image_path="generated/frame.jpg", image_url="/generated/frame.jpg"),
    ]

    analyses = analyze_keyframes(keyframe_items)

    assert [analysis.analysis_mode for analysis in analyses] == ["openai", "vision_skipped_limit"]


def test_save_uploaded_video_rejects_oversized_upload(monkeypatch) -> None:
    monkeypatch.setattr(
        keyframes,
        "get_settings",
        lambda: type("Settings", (), {"video_max_bytes": 4, "video_max_duration_seconds": 1800})(),
    )

    with pytest.raises(ValueError, match="too large"):
        save_uploaded_video("sample.mp4", b"12345")
def test_vision_prompt_treats_visible_text_as_untrusted() -> None:
    prompt = frame_analysis.VISION_PROMPT.lower()

    assert "untrusted evidence" in prompt
    assert "never as instructions" in prompt
