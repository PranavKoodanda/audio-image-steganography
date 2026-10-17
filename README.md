# Audio-in-Image Steganography

Audio-in-Image Steganography is a Python project for securely packaging an
arbitrary binary payload, such as a WAV file, inside a PNG image. The current
implementation provides the cryptographic, PNG container, pixel-based
steganography, and FastAPI backend foundations; the user interface is planned
for a later phase.

## Implemented features

- **AES-256-GCM encryption:** Encrypts binary payloads with confidentiality and
  authenticated integrity. Wrong passwords or modified authenticated data are
  rejected.
- **Password-based key derivation:** Derives a 256-bit key with Scrypt using a
  fresh random 16-byte salt for every encryption. The default parameters are
  `N=2^16`, `r=8`, and `p=1`.
- **Versioned binary envelope:** Stores the salt, nonce, KDF parameters,
  ciphertext, and authentication tag without storing the password or derived
  key. Envelope versions, lengths, KDF bounds, and payload size are validated
  before expensive cryptographic processing.
- **SHA-256 utilities:** Provides hexadecimal and raw-digest helpers for
  verifying byte-for-byte payload recovery.
- **PNG custom-chunk embedding:** Stores arbitrary binary data in a `stEg`
  ancillary PNG chunk immediately before `IEND`. Existing PNG chunks are
  preserved byte-for-byte, and embedding does not decode or re-encode image
  pixels. Extraction validates chunk boundaries and CRC-32 values, rejects
  missing or duplicate payloads, and requires the payload chunk to be directly
  before `IEND`.
- **LSB pixel embedding:** Stores arbitrary binary data in RGB channels of RGB
  or RGBA PNG images, with a versioned header containing a magic identifier,
  payload length, and SHA-256 checksum. Use `calculate_capacity(image)` before
  calling `embed_lsb(image, payload)`, then call `extract_lsb(image)` to recover
  the exact bytes. The checksum detects accidental corruption, but is not
  authentication; use the Phase 1 AES-GCM envelope for that security boundary.
- **Image-quality measurements:** `calculate_image_metrics(first, second)`
  reports changed RGB channels, changed-channel ratio, mean squared error
  (MSE), and peak signal-to-noise ratio (PSNR), excluding alpha from the
  comparison.
- **End-to-end WAV workflow:** `hide_wav_in_png(wav_data, png, password,
  method)` encrypts valid WAV bytes and embeds the authenticated envelope using
  either `chunk` or `lsb`. `recover_wav_from_png(png, password, method)`
  extracts, authenticates, decrypts, and validates the WAV before returning
  the exact original bytes. Passwords are never stored or logged.
- **FastAPI backend:** `GET /api/health` reports API availability. `POST
  /api/hide` accepts multipart `wav`, `image`, `password`, and `method` fields
  and returns a downloadable `stego.png`. `POST /api/recover` accepts
  multipart `image`, `password`, and `method` fields and returns a downloadable
  `recovered.wav`. The API validates uploaded content, maps workflow failures
  to controlled HTTP errors, and never logs or stores passwords.
- **React frontend:** A Vite-powered desktop-first workbench provides hide and
  recover workflows, drag-and-drop WAV/PNG selection, method and password
  controls, API health status, error feedback, and real blob downloads from the
  backend. Its Nebula Core dark cybersecurity workbench theme uses a sticky
  navigation bar, restrained indigo/cyan depth, responsive two-column
  workspace, high-contrast form states, and reduced-motion support. Passwords
  remain in component memory only.

## Workflow

The intended current workflow is:

```text
binary payload (for example, WAV)
        │
        ▼
AES-256-GCM encryption with a password
        │
        ▼
versioned encrypted envelope
        │
        ▼
PNG stEg ancillary-chunk embedding or LSB pixel embedding
        │
        ▼
PNG containing the encrypted payload
```

On recovery, the `stEg` payload is extracted and then passed to the envelope
decryption routine. PNG CRC-32 detects chunk corruption, while AES-GCM
authentication provides the security boundary for detecting tampering and
incorrect passwords.

Example Python usage:

```python
from backend.app.services.workflow import hide_wav_in_png, recover_wav_from_png

with open("input.wav", "rb") as wav_file, open("cover.png", "rb") as png_file:
    embedded_png = hide_wav_in_png(wav_file.read(), png_file.read(), "password", "chunk")

recovered_wav = recover_wav_from_png(embedded_png, "password", "chunk")
with open("recovered.wav", "wb") as wav_file:
    wav_file.write(recovered_wav)
```

Use `method="lsb"` for pixel-based embedding. LSB modifies RGB pixel values
slightly and can be damaged by resizing or re-encoding. Custom `stEg` chunks
can be stripped by image-processing or upload services. Neither method
guarantees invisibility or resistance to steganalysis.

## Technology and structure

- Python 3.13 is the currently tested environment.
- [`cryptography`](https://cryptography.io/) provides AES-GCM and Scrypt.
- FastAPI and Uvicorn provide the HTTP API and development server.
- `pytest` provides automated tests.
- Pillow decodes RGB/RGBA images for LSB embedding and image comparisons.
  PNG chunk embedding still operates on bytes without rewriting pixels.

```text
backend/
├── app/
│   ├── main.py             # FastAPI application and HTTP endpoints
│   ├── core/
│   │   ├── crypto.py       # AES-GCM encryption and Scrypt key derivation
│   │   ├── envelope.py     # Versioned encrypted-envelope format
│   │   └── validation.py   # Shared input validation
│   ├── stego/
│   │   ├── png_chunk.py    # PNG stEg chunk embedding and extraction
│   │   └── lsb.py          # RGB/RGBA LSB embedding and extraction
│   ├── services/
│   │   └── workflow.py      # End-to-end encrypted WAV workflows
│   └── utils/
│       ├── hashing.py       # SHA-256 helpers
│       └── image_metrics.py # Pixel differences and quality metrics
├── tests/
│   ├── test_api.py
│   ├── test_crypto.py
│   ├── test_lsb.py
│   └── test_png_chunk.py
│   └── test_workflow.py
└── requirements.txt
```

The frontend is in `frontend/` and uses React with Vite. It does not duplicate
encryption or steganography logic; all operations go through the FastAPI API.

## Setup and tests

From the repository root on Windows:

```powershell
py -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
backend\.venv\Scripts\python.exe -m pytest backend\tests -q
```

With an already configured Python environment:

```powershell
python -m pytest backend\tests -q
```

Run the API from the repository root after installing
`backend\requirements.txt`:

```powershell
backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

Run the frontend in a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

In local development, the Vite server proxies relative `/api` requests to
`http://127.0.0.1:8000`, so no CORS configuration is required. Set
`VITE_API_BASE_URL` in a frontend `.env` file to use an absolute backend URL
for deployments or a different development setup; when set, requests use that
URL directly instead of the Vite proxy.

Interactive API documentation is available at `http://127.0.0.1:8000/docs`.
Both embedding methods use the `method` form field with either `chunk` or
`lsb`; wrong passwords, invalid files, malformed payloads, and insufficient
LSB capacity return controlled errors rather than stack traces.

The API limits each uploaded WAV and PNG file to 20 MiB by default. These
limits are defined as `MAX_WAV_UPLOAD_SIZE` and `MAX_PNG_UPLOAD_SIZE` in
`backend/app/main.py` and can be adjusted before starting the server. Uploads
are read incrementally in bounded chunks; files exceeding a configured limit
are rejected with HTTP `413 Payload Too Large` before workflow processing.

## Limitations and security considerations

- PNG chunk embedding does not encrypt data by itself. Use the encrypted
  envelope before embedding confidential payloads.
- PNG CRC-32 detects accidental corruption but is not cryptographic
  authentication. AES-GCM authentication must be checked during recovery.
- The parser validates chunk structure and CRCs, but it is not a complete PNG
  decoder or semantic validator.
- Unknown ancillary chunks, including `stEg`, may be stripped by image
  optimization, upload, conversion, or social-media services.
- The current implementation loads PNG and payload bytes in memory and limits
  individual chunk data to 256 MiB.
- No password, derived key, audio validation, or payload metadata is stored in
  the PNG chunk.

PNG chunk embedding preserves decoded pixels, while LSB embedding changes
some RGB values slightly and preserves alpha. Re-encoding an image may change
metadata and can discard either embedded representation. Chunk embedding has
more direct byte capacity and no pixel changes; LSB embedding is a
pixel-based alternative whose capacity depends on image dimensions and whose
changes can be measured with the image-quality helpers.

The backend-specific notes are kept in
[`backend/README.md`](backend/README.md); this file is the primary project
documentation.
