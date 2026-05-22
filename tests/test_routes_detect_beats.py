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
