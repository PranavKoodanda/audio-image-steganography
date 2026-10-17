# Audio-in-Image Steganography

Audio-in-Image Steganography is a Python project for securely packaging an
arbitrary binary payload, such as a WAV file, inside a PNG image. The current
implementation provides the cryptographic and PNG container foundations; the
application API, user interface, and pixel-based steganography are planned for
later phases.

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
PNG stEg ancillary-chunk embedding
        │
        ▼
PNG containing the encrypted payload
```

On recovery, the `stEg` payload is extracted and then passed to the envelope
decryption routine. PNG CRC-32 detects chunk corruption, while AES-GCM
authentication provides the security boundary for detecting tampering and
incorrect passwords.

## Technology and structure

- Python 3.13 is the currently tested environment.
- [`cryptography`](https://cryptography.io/) provides AES-GCM and Scrypt.
- `pytest` provides automated tests.
- Pillow is used only by tests to create PNG fixtures and compare decoded
  pixels; it is not used to rewrite PNGs during embedding.

```text
backend/
├── app/
│   ├── core/
│   │   ├── crypto.py       # AES-GCM encryption and Scrypt key derivation
│   │   ├── envelope.py     # Versioned encrypted-envelope format
│   │   └── validation.py   # Shared input validation
│   ├── stego/
│   │   └── png_chunk.py    # PNG stEg chunk embedding and extraction
│   └── utils/
│       └── hashing.py      # SHA-256 helpers
├── tests/
│   ├── test_crypto.py
│   └── test_png_chunk.py
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

- LSB pixel steganography, capacity checks, pixel-difference reporting, and
  image-quality metrics.
- FastAPI backend endpoints.
- React and Vite frontend.
- End-to-end audio upload, recovery, and user-facing workflow.

The backend-specific notes are kept in
[`backend/README.md`](backend/README.md); this file is the primary project
documentation.
