"""Tests for POST /api/plugins/editor/detect-beats."""
import json
from pathlib import Path


def _stock_response():
    return {
        "beats": [{"time": 0.5, "downbeat": True, "beat_in_bar": 1}],
        "mean_bpm": 120.0,
        "bpm_curve": [[0.5, 120.0]],
        "audio_duration": 3.0,
        "detector": "fake",
        "detector_version": "0.0.0",
    }


def test_returns_503_when_provider_not_installed(client, session_dir):
    """When no provider plugin is mounted on the app, the route returns 503
    with a copyable install_hint — never a 500 or unhandled exception."""
    response = client.post(
        "/api/plugins/editor/detect-beats",
        json={"session_id": "test_session", "force": False},
    )
    assert response.status_code == 503
    body = response.json()
    assert body["error"] == "sidecar_unavailable"
    assert "install_hint" in body
    assert "auto-align" in body["install_hint"].lower()


def test_happy_path_with_provider(client_with_provider, session_dir):
    """When provider is mounted, route reads session audio, calls provider,
    returns the provider's response verbatim."""
    response = client_with_provider.post(
        "/api/plugins/editor/detect-beats",
        json={"session_id": "test_session", "force": False},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["detector"] == "fake"
    assert len(body["beats"]) == 5
    assert body["beats"][0]["downbeat"] is True
    assert body["mean_bpm"] == 120.0


def test_cache_hit_on_repeat_call(client_with_provider, session_dir, monkeypatch):
    """Second call with force=False returns the cached body and does NOT
    re-invoke the provider."""
    r1 = client_with_provider.post(
        "/api/plugins/editor/detect-beats",
        json={"session_id": "test_session", "force": False},
    )
    assert r1.status_code == 200
    cache_file = session_dir / "beats_detected.json"
    assert cache_file.exists()

    # Mutate the cache so we can prove subsequent calls read from it.
    cached = json.loads(cache_file.read_text())
    cached["detector"] = "from_cache"
    cache_file.write_text(json.dumps(cached))

    # Force the cache file's mtime to be newer than the audio's so the
    # mtime-keyed invalidation path doesn't bypass the cache.
    audio = next(session_dir.glob("audio.*"))
    import os
    os.utime(audio, (cache_file.stat().st_mtime - 10, cache_file.stat().st_mtime - 10))

    r2 = client_with_provider.post(
        "/api/plugins/editor/detect-beats",
        json={"session_id": "test_session", "force": False},
    )
    assert r2.status_code == 200
    assert r2.json()["detector"] == "from_cache"


def test_force_bypasses_cache(client_with_provider, session_dir):
    """force=true re-calls the provider even if cache exists."""
    cache_file = session_dir / "beats_detected.json"
    cache_file.write_text(json.dumps({
        "beats": [], "mean_bpm": 999, "bpm_curve": [],
        "audio_duration": 0, "detector": "stale", "detector_version": "0",
    }))

    r = client_with_provider.post(
        "/api/plugins/editor/detect-beats",
        json={"session_id": "test_session", "force": True},
    )
    assert r.status_code == 200
    assert r.json()["detector"] == "fake"


def test_cache_invalidated_when_audio_newer(client_with_provider, session_dir):
    """If audio mtime is newer than cache mtime, cache is invalidated."""
    import os
    cache_file = session_dir / "beats_detected.json"
    cache_file.write_text(json.dumps({
        "beats": [], "mean_bpm": 999, "bpm_curve": [],
        "audio_duration": 0, "detector": "stale", "detector_version": "0",
    }))
    # Make audio newer than cache.
    audio = next(session_dir.glob("audio.*"))
    future = cache_file.stat().st_mtime + 60
    os.utime(audio, (future, future))

    r = client_with_provider.post(
        "/api/plugins/editor/detect-beats",
        json={"session_id": "test_session", "force": False},
    )
    assert r.status_code == 200
    assert r.json()["detector"] == "fake"  # cache was bypassed


def test_provider_5xx_becomes_502(app_factory, session_dir):
    """If provider returns 500/503/etc, editor returns 502 detection_failed
    (relayed body in detail when available)."""
    from fastapi.testclient import TestClient
    app = app_factory(with_provider=True, provider_status=500)
    client = TestClient(app)

    r = client.post(
        "/api/plugins/editor/detect-beats",
        json={"session_id": "test_session", "force": True},
    )
    assert r.status_code == 502
    assert r.json()["error"] == "detection_failed"


def test_provider_returns_empty_beats_is_200(app_factory, session_dir):
    """Empty `beats` list is a valid 200 response."""
    from fastapi.testclient import TestClient
    empty_response = {
        "beats": [], "mean_bpm": 0.0, "bpm_curve": [],
        "audio_duration": 3.0, "detector": "fake", "detector_version": "0.0.0",
    }
    app = app_factory(with_provider=True, provider_response=empty_response)
    client = TestClient(app)

    r = client.post(
        "/api/plugins/editor/detect-beats",
        json={"session_id": "test_session", "force": True},
    )
    assert r.status_code == 200
    assert r.json()["beats"] == []


def test_static_file_route_serves_align_warp(client):
    """The /static/{name} route serves plugin-local JS files."""
    r = client.get("/api/plugins/editor/static/align-warp.js")
    assert r.status_code == 200
    assert "warpTabToAudioBeats" in r.text


def test_static_file_route_rejects_path_traversal(client):
    """Path traversal attempts return 403."""
    r = client.get("/api/plugins/editor/static/../routes.py")
    # FastAPI normalizes the path before it reaches the handler, so the
    # traversal either gets rejected by the path-prefix check (403) OR
    # FastAPI itself returns a 404 because the normalized path doesn't
    # match a route. Either is acceptable security behavior.
    assert r.status_code in (403, 404)


def test_create_mode_resolves_audio_from_url(
    app_factory, session_dir, silent_wav_bytes, tmp_path
):
    """Create-mode sessions have audio_file=None until Build runs. The route
    must accept an audio_url and resolve it via _resolve_storage_url so the
    feature works without a Build."""
    from fastapi.testclient import TestClient

    # Remove the default audio.wav so the last-ditch scan can't find it —
    # we want to exercise the audio_url path specifically.
    for candidate in session_dir.glob("audio.*"):
        candidate.unlink()

    # _resolve_storage_url maps audio_url back to a filesystem path. Two
    # paths are valid:
    #   /static/X            → <slopsmith>/static/X (active when the static
    #                          dir is writable AND has the app.js sentinel)
    #   /api/plugins/editor/cache/X → <config_dir>/editor_cache/X (fallback)
    # Test env satisfies the legacy path, prod (.exe / non-standard install)
    # uses the cache path. Write to both so this test passes regardless.
    legacy_static = (
        Path(__file__).resolve().parent.parent.parent.parent / "static"
    )
    cache_dir = tmp_path / "config" / "editor_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    audio_name = "editor_audio_test_autoalign.wav"
    legacy_file = legacy_static / audio_name
    cache_file = cache_dir / audio_name
    legacy_file.write_bytes(silent_wav_bytes)
    cache_file.write_bytes(silent_wav_bytes)

    try:
        app = app_factory(with_provider=True, provider_response=_stock_response())
        client = TestClient(app)

        # Simulate create-mode: clear audio_file so we exercise the audio_url path.
        import routes
        routes._sessions["test_session"]["audio_file"] = None
        routes._sessions["test_session"]["create_mode"] = True

        # Try /static/ first (the form used when the legacy static dir is
        # active). If the route's storage probe picked the cache fallback,
        # retry with the cache URL.
        r = client.post(
            "/api/plugins/editor/detect-beats",
            json={
                "session_id": "test_session",
                "force": True,
                "audio_url": f"/static/{audio_name}",
            },
        )
        if r.status_code != 200:
            r = client.post(
                "/api/plugins/editor/detect-beats",
                json={
                    "session_id": "test_session",
                    "force": True,
                    "audio_url": f"/api/plugins/editor/cache/{audio_name}",
                },
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["detector"] == "fake"
    finally:
        legacy_file.unlink(missing_ok=True)


def test_create_mode_without_audio_url_returns_diagnostic(
    app_factory, session_dir
):
    """Create-mode session without audio_file AND without audio_url → 404
    with diagnostic showing create_mode: true and audio_url_hint empty."""
    from fastapi.testclient import TestClient

    # Remove the default audio.wav so the last-ditch scan can't find it.
    for candidate in session_dir.glob("audio.*"):
        candidate.unlink()

    app = app_factory(with_provider=True, provider_response=_stock_response())
    client = TestClient(app)

    import routes
    routes._sessions["test_session"]["audio_file"] = None
    routes._sessions["test_session"]["create_mode"] = True

    r = client.post(
        "/api/plugins/editor/detect-beats",
        json={"session_id": "test_session", "force": True},
    )
    assert r.status_code == 404
    body = r.json()
    assert body["error"] == "audio_missing"
    assert body["diagnostic"]["create_mode"] is True
    assert body["diagnostic"]["audio_file_value"] is None
    assert body["diagnostic"]["audio_url_hint"] == ""
