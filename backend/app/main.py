"""FastAPI application for the audio-in-image steganography workflow."""

from collections.abc import Callable
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from backend.app.core.crypto import AuthenticationError
from backend.app.core.envelope import EnvelopeError
from backend.app.services.workflow import (
    InvalidPNGError,
    InvalidWAVError,
    UnsupportedMethodError,
    hide_wav_in_png,
    recover_wav_from_png,
)
from backend.app.stego.lsb import LSBError
from backend.app.stego.png_chunk import PNGChunkError

app = FastAPI(
    title="Audio Image Steganography API",
    description="Encrypt WAV audio and hide it in PNG images.",
)

Method = Literal["chunk", "lsb"]
WorkflowCallable = Callable[..., bytes]
MAX_WAV_UPLOAD_SIZE = 20 * 1024 * 1024
MAX_PNG_UPLOAD_SIZE = 20 * 1024 * 1024
UPLOAD_READ_CHUNK_SIZE = 1024 * 1024


async def _read_upload(
    upload: UploadFile,
    field_name: str,
    max_size: int,
) -> bytes:
    data = bytearray()
    try:
        while True:
            remaining = max_size - len(data)
            chunk = await upload.read(min(UPLOAD_READ_CHUNK_SIZE, remaining + 1))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > max_size:
                raise HTTPException(
                    status_code=413,
                    detail=f"{field_name} upload exceeds the {max_size} byte limit",
                )
    except OSError as error:
        raise HTTPException(
            status_code=400,
            detail=f"could not read {field_name} upload",
        ) from error
    if not data:
        raise HTTPException(status_code=400, detail=f"{field_name} upload is empty")
    return bytes(data)


def _run_workflow(workflow: WorkflowCallable, *args: object) -> bytes:
    try:
        return workflow(*args)
    except AuthenticationError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    except (
        EnvelopeError,
        InvalidPNGError,
        InvalidWAVError,
        LSBError,
        PNGChunkError,
        UnsupportedMethodError,
        TypeError,
        ValueError,
    ) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Report that the API is available."""
    return {"status": "ok"}


@app.post("/api/hide")
async def hide(
    wav: UploadFile = File(..., description="PCM WAV audio to encrypt and hide"),
    image: UploadFile = File(..., description="PNG cover image"),
    password: str = Form(..., description="Password used for AES-GCM encryption"),
    method: Method = Form(..., description="Embedding method: chunk or lsb"),
) -> Response:
    """Encrypt an uploaded WAV and return a PNG containing the encrypted data."""
    wav_data = await _read_upload(wav, "wav", MAX_WAV_UPLOAD_SIZE)
    image_data = await _read_upload(image, "image", MAX_PNG_UPLOAD_SIZE)
    stego_png = _run_workflow(
        hide_wav_in_png,
        wav_data,
        image_data,
        password,
        method,
    )
    return Response(
        content=stego_png,
        media_type="image/png",
        headers={"Content-Disposition": 'attachment; filename="stego.png"'},
    )


@app.post("/api/recover")
async def recover(
    image: UploadFile = File(..., description="PNG containing encrypted audio"),
    password: str = Form(..., description="Password used for AES-GCM decryption"),
    method: Method = Form(..., description="Embedding method: chunk or lsb"),
) -> Response:
    """Recover and return the decrypted WAV from an uploaded stego PNG."""
    image_data = await _read_upload(image, "image", MAX_PNG_UPLOAD_SIZE)
    wav_data = _run_workflow(
        recover_wav_from_png,
        image_data,
        password,
        method,
    )
    return Response(
        content=wav_data,
        media_type="audio/wav",
        headers={"Content-Disposition": 'attachment; filename="recovered.wav"'},
    )
