"""Tests for POST /api/plugins/editor/detect-beats."""
import json
from pathlib import Path


def test_returns_503_when_provider_not_installed(client, session_dir):
    """When no provider plugin is mounted on the app, the route returns 503
    with a copyable install_hint — never a 500 or unhandled exception."""
    response = client.post(
        "/api/plugins/editor/detect-beats",
        json={"session": str(session_dir), "force": False},
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
        json={"session": str(session_dir), "force": False},
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
        json={"session": str(session_dir), "force": False},
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
        json={"session": str(session_dir), "force": False},
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
        json={"session": str(session_dir), "force": True},
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
        json={"session": str(session_dir), "force": False},
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
        json={"session": str(session_dir), "force": True},
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
        json={"session": str(session_dir), "force": True},
    )
    assert r.status_code == 200
    assert r.json()["beats"] == []
