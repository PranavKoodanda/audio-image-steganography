# Audio-in-Image Steganography

Audio-in-Image Steganography is a Python project for securely packaging an
arbitrary binary payload, such as a WAV file, inside a PNG image. The current
implementation provides the cryptographic, PNG container, and pixel-based
steganography foundations; the application API and user interface are planned
for later phases.

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
- `pytest` provides automated tests.
- Pillow decodes RGB/RGBA images for LSB embedding and image comparisons.
  PNG chunk embedding still operates on bytes without rewriting pixels.

```text
backend/
├── app/
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
│   ├── test_crypto.py
│   ├── test_lsb.py
│   └── test_png_chunk.py
│   └── test_workflow.py
└── requirements.txt
```

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

## Planned features

The following are not implemented yet:

- FastAPI backend endpoints.
- React and Vite frontend.
- User-facing upload/recovery interface and GUI.

PNG chunk embedding preserves decoded pixels, while LSB embedding changes
some RGB values slightly and preserves alpha. Re-encoding an image may change
metadata and can discard either embedded representation. Chunk embedding has
more direct byte capacity and no pixel changes; LSB embedding is a
pixel-based alternative whose capacity depends on image dimensions and whose
changes can be measured with the image-quality helpers.

The backend-specific notes are kept in
[`backend/README.md`](backend/README.md); this file is the primary project
documentation.
