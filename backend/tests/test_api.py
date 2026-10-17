import asyncio
from io import BytesIO
import wave

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from PIL import Image

from backend.app import main as api
from backend.app.main import _read_upload, app
from backend.app.services.workflow import hide_wav_in_png


PASSWORD = "api password"
client = TestClient(app)


def _wav() -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00\x10\x00\x20\x00\x30\x00")
    return output.getvalue()


def _png(size: tuple[int, int] = (256, 256)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, (40, 80, 120)).save(output, format="PNG")
    return output.getvalue()


@pytest.mark.parametrize("method", ["chunk", "lsb"])
def test_hide_and_recover_endpoints_round_trip(method: str) -> None:
    hide_response = client.post(
        "/api/hide",
        files={
            "wav": ("input.wav", _wav(), "audio/wav"),
            "image": ("cover.png", _png(), "image/png"),
        },
        data={"password": PASSWORD, "method": method},
    )

    assert hide_response.status_code == 200
    assert hide_response.headers["content-type"] == "image/png"
    assert 'filename="stego.png"' in hide_response.headers["content-disposition"]

    recover_response = client.post(
        "/api/recover",
        files={"image": ("stego.png", hide_response.content, "image/png")},
        data={"password": PASSWORD, "method": method},
    )

    assert recover_response.status_code == 200
    assert recover_response.headers["content-type"] == "audio/wav"
    assert 'filename="recovered.wav"' in recover_response.headers["content-disposition"]
    assert recover_response.content == _wav()


def test_health_endpoint() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_hide_rejects_missing_fields() -> None:
    response = client.post("/api/hide", data={"password": PASSWORD, "method": "chunk"})

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("path", "files", "data", "expected_status"),
    [
        (
            "/api/hide",
            {
                "wav": ("input.wav", b"not wav", "audio/wav"),
                "image": ("cover.png", _png(), "image/png"),
            },
            {"password": PASSWORD, "method": "chunk"},
            400,
        ),
        (
            "/api/hide",
            {
                "wav": ("input.wav", _wav(), "audio/wav"),
                "image": ("cover.png", b"not png", "image/png"),
            },
            {"password": PASSWORD, "method": "chunk"},
            400,
        ),
        (
            "/api/recover",
            {"image": ("stego.png", b"not png", "image/png")},
            {"password": PASSWORD, "method": "chunk"},
            400,
        ),
    ],
)
def test_endpoints_reject_invalid_files(
    path: str,
    files: dict[str, tuple[str, bytes, str]],
    data: dict[str, str],
    expected_status: int,
) -> None:
    response = client.post(path, files=files, data=data)

    assert response.status_code == expected_status
    assert "detail" in response.json()


def test_recover_rejects_wrong_password_without_returning_audio() -> None:
    stego_png = hide_wav_in_png(_wav(), _png(), PASSWORD, "chunk")

    response = client.post(
        "/api/recover",
        files={"image": ("stego.png", stego_png, "image/png")},
        data={"password": "wrong password", "method": "chunk"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid password or tampered encrypted payload"


def test_hide_rejects_unsupported_method() -> None:
    response = client.post(
        "/api/hide",
        files={
            "wav": ("input.wav", _wav(), "audio/wav"),
            "image": ("cover.png", _png(), "image/png"),
        },
        data={"password": PASSWORD, "method": "unsupported"},
    )

    assert response.status_code == 422


def test_lsb_capacity_failure_is_reported() -> None:
    response = client.post(
        "/api/hide",
        files={
            "wav": ("input.wav", _wav(), "audio/wav"),
            "image": ("cover.png", _png((8, 8)), "image/png"),
        },
        data={"password": PASSWORD, "method": "lsb"},
    )

    assert response.status_code == 400
    assert "LSB" in response.json()["detail"]


def test_hide_rejects_oversized_wav_upload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "MAX_WAV_UPLOAD_SIZE", 8)

    response = client.post(
        "/api/hide",
        files={
            "wav": ("input.wav", b"123456789", "audio/wav"),
            "image": ("cover.png", _png(), "image/png"),
        },
        data={"password": PASSWORD, "method": "chunk"},
    )

    assert response.status_code == 413
    assert "wav upload exceeds" in response.json()["detail"]


def test_hide_rejects_oversized_png_upload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "MAX_PNG_UPLOAD_SIZE", 8)

    response = client.post(
        "/api/hide",
        files={
            "wav": ("input.wav", _wav(), "audio/wav"),
            "image": ("cover.png", b"123456789", "image/png"),
        },
        data={"password": PASSWORD, "method": "chunk"},
    )

    assert response.status_code == 413
    assert "image upload exceeds" in response.json()["detail"]


def test_recover_rejects_oversized_png_upload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "MAX_PNG_UPLOAD_SIZE", 8)

    response = client.post(
        "/api/recover",
        files={"image": ("stego.png", b"123456789", "image/png")},
        data={"password": PASSWORD, "method": "chunk"},
    )

    assert response.status_code == 413
    assert "image upload exceeds" in response.json()["detail"]


def test_upload_reader_accepts_data_exactly_at_limit() -> None:
    upload = UploadFile(file=BytesIO(b"123456789"))

    result = asyncio.run(_read_upload(upload, "test", 9))

    assert result == b"123456789"


def test_upload_reader_rejects_one_byte_over_limit() -> None:
    upload = UploadFile(file=BytesIO(b"1234567890"))

    with pytest.raises(HTTPException) as caught:
        asyncio.run(_read_upload(upload, "test", 9))

    assert caught.value.status_code == 413
