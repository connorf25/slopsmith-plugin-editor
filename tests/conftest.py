"""Test fixtures for the auto-align editor-side feature.

Each test gets a fresh FastAPI app with the editor's routes mounted.
A `fake_provider` fixture optionally mounts a stub auto-align provider
on the same app so we can exercise the forwarding logic end-to-end
without depending on the real provider plugin.
"""
import io
import json
import sys
import wave
from pathlib import Path
import tempfile
import shutil
import os

sys.path.insert(0, str(Path("/Users/connorforbes/Documents/GitHub/slopsmith")))
sys.path.insert(0, str(Path("/Users/connorforbes/Documents/GitHub/slopsmith/lib")))

import pytest
from fastapi import FastAPI, UploadFile, File
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Audio fixture: a 3-second silent WAV file, generated once per session.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def silent_wav_bytes():
    """3-second silent mono 22050 Hz WAV — used as a stand-in audio file."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x00\x00" * 22050 * 3)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Session directory: an isolated tmp dir mimicking the editor's session layout.
# ---------------------------------------------------------------------------

@pytest.fixture
def session_dir(tmp_path, silent_wav_bytes):
    """A throwaway session dir containing one audio file."""
    audio = tmp_path / "audio.wav"
    audio.write_bytes(silent_wav_bytes)
    return tmp_path


# ---------------------------------------------------------------------------
# App fixture: a fresh FastAPI app with the editor's routes mounted.
# The context dict is minimal — only the fields the editor's setup() reads.
# ---------------------------------------------------------------------------

@pytest.fixture
def app_factory(tmp_path):
    """Returns a function that builds a fresh FastAPI app each call.

    Allows tests to opt in to mounting a fake provider on the same app
    before the editor's routes are registered (mount order doesn't
    actually matter for in-process route lookup, but explicit is clearer).
    """
    from routes import setup as editor_setup  # noqa: WPS433 — plugin's own setup

    def _make(*, with_provider=False, provider_response=None, provider_status=200,
              provider_health_loaded=True):
        app = FastAPI()

        if with_provider:
            _mount_fake_provider(
                app,
                response=provider_response,
                status=provider_status,
                health_loaded=provider_health_loaded,
            )

        context = {
            "config_dir": tmp_path / "config",
            "get_dlc_dir": lambda: tmp_path / "dlc",
        }
        (tmp_path / "config").mkdir(exist_ok=True)
        (tmp_path / "dlc").mkdir(exist_ok=True)

        editor_setup(app, context)
        return app

    return _make


@pytest.fixture
def client(app_factory):
    """Default client: editor only, no provider mounted."""
    return TestClient(app_factory())


@pytest.fixture
def client_with_provider(app_factory):
    """Default client with a healthy fake provider returning a stock response."""
    return TestClient(app_factory(
        with_provider=True,
        provider_response=_stock_provider_response(),
    ))


# ---------------------------------------------------------------------------
# Fake provider: a minimal stub satisfying the contract.
# ---------------------------------------------------------------------------

def _stock_provider_response():
    return {
        "beats": [
            {"time": 0.5, "downbeat": True, "beat_in_bar": 1},
            {"time": 1.0, "downbeat": False, "beat_in_bar": 2},
            {"time": 1.5, "downbeat": False, "beat_in_bar": 3},
            {"time": 2.0, "downbeat": False, "beat_in_bar": 4},
            {"time": 2.5, "downbeat": True, "beat_in_bar": 1},
        ],
        "mean_bpm": 120.0,
        "bpm_curve": [[0.5, 120.0], [1.0, 120.0]],
        "audio_duration": 3.0,
        "detector": "fake",
        "detector_version": "0.0.0",
    }


def _mount_fake_provider(app, *, response, status, health_loaded):
    @app.get("/api/plugins/auto-align/health")
    async def _health():
        from fastapi.responses import JSONResponse
        return JSONResponse(
            {"status": "ok" if health_loaded else "loading",
             "detector": "fake",
             "detector_version": "0.0.0",
             "model_loaded": health_loaded},
            status_code=200,
        )

    @app.post("/api/plugins/auto-align/detect-beats")
    async def _detect(audio: UploadFile = File(...)):
        from fastapi.responses import JSONResponse
        if status == 200:
            return response
        return JSONResponse(
            {"error": "detection_failed", "detail": "fake error"},
            status_code=status,
        )
