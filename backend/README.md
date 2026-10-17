# Audio-in-Image Steganography Backend

This increment provides the encrypted payload foundation and direct PNG custom
ancillary-chunk embedding. LSB steganography, FastAPI endpoints, and the React
frontend are intentionally deferred.

`app.stego.png_chunk` inserts arbitrary bytes into a valid `stEg` ancillary
chunk immediately before `IEND`. It parses and validates the existing PNG
without decoding or re-encoding it, so all original chunks remain byte-for-byte
unchanged and decoded pixels remain unchanged. Embedding rejects an image that
already contains `stEg`; extraction rejects missing or duplicate payload
chunks.

## Encryption design

`app.core.crypto` uses AES-256-GCM with a new 16-byte random salt and 12-byte
random nonce for every encryption. The password is UTF-8 encoded and processed
with Scrypt using `N=2^16`, `r=8`, and `p=1` by default. No password or
derived key is written to the envelope.

The versioned binary envelope begins with a fixed big-endian header containing
the algorithm identifiers, component lengths, Scrypt parameters, and
ciphertext length. The header is authenticated as AES-GCM additional
authenticated data. Parsing validates all lengths and bounds before Scrypt is
run; ciphertext is capped at 256 MiB.

Authentication failures (wrong password or modified authenticated data) raise
`AuthenticationError`. Structural problems raise `EnvelopeError`.

## Setup and tests

From the repository root on Windows:

```powershell
py -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
backend\.venv\Scripts\python.exe -m pytest backend\tests
```

When using an already configured interpreter from the repository root:

```powershell
python -m pytest backend\tests
```
