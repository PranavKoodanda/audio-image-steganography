import { useEffect, useRef, useState } from "react";
import { checkHealth, hideAudio, recoverAudio } from "./api";

const METHODS = [
  {
    id: "chunk",
    name: "PNG Chunk",
    description: "Stores the encrypted payload in a custom PNG chunk.",
  },
  {
    id: "lsb",
    name: "LSB",
    description: "Embeds payload bits in image pixels; capacity depends on dimensions.",
  },
];

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function ProductMark() {
  return <span className="product-mark" aria-hidden="true"><span /></span>;
}

function StatusIndicator({ status }) {
  const labels = { checking: "Checking API", connected: "API connected", unavailable: "API unavailable" };
  return (
    <div className={`api-status ${status}`} role="status">
      <span className="status-dot" />
      {labels[status]}
    </div>
  );
}

function PasswordField({ value, onChange, id }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="password-wrap">
      <input
        id={id}
        type={visible ? "text" : "password"}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete="off"
        required
      />
      <button
        className="visibility-button"
        type="button"
        onClick={() => setVisible((current) => !current)}
        aria-label={visible ? "Hide password" : "Show password"}
      >
        {visible ? "Hide" : "Show"}
      </button>
    </div>
  );
}

function FileDrop({ id, label, accept, file, onFile, onRemove, hint, preview }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  useEffect(() => {
    if (!file && inputRef.current) inputRef.current.value = "";
  }, [file]);

  const chooseFile = (candidate) => {
    if (candidate && candidate.type) onFile(candidate);
  };
  return (
    <div className="field-group">
      <div className="field-heading">
        <label htmlFor={id}>{label}</label>
        <span>{hint}</span>
      </div>
      <div
        className={`drop-zone ${dragging ? "dragging" : ""} ${file ? "has-file" : ""}`}
        onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          chooseFile(event.dataTransfer.files[0]);
        }}
      >
        <input
          ref={inputRef}
          id={id}
          type="file"
          accept={accept}
          onChange={(event) => chooseFile(event.target.files[0])}
        />
        {file ? (
          <div className="file-selected">
            {preview}
            <div className="file-details">
              <strong>{file.name}</strong>
              <span>{formatBytes(file.size)}</span>
            </div>
            <button
              type="button"
              className="text-button"
              onClick={() => {
                inputRef.current.value = "";
                onRemove();
              }}
            >
              Remove
            </button>
          </div>
        ) : (
          <button type="button" className="drop-action" onClick={() => inputRef.current?.click()}>
            <span className="upload-glyph" aria-hidden="true">↑</span>
            <span><strong>Drop file here</strong> or browse</span>
            <small>{accept === ".wav,audio/wav" ? "WAV audio only" : "PNG image only"}</small>
          </button>
        )}
      </div>
    </div>
  );
}

function MethodSelector({ method, onChange }) {
  return (
    <fieldset className="field-group method-field">
      <legend>Embedding method</legend>
      <div className="method-options">
        {METHODS.map((option) => (
          <label className={`method-option ${method === option.id ? "selected" : ""}`} key={option.id}>
            <input
              type="radio"
              name="method"
              value={option.id}
              checked={method === option.id}
              onChange={() => onChange(option.id)}
            />
            <span className="radio-mark" />
            <span><strong>{option.name}</strong><small>{option.description}</small></span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function Result({ type, blob, onReset }) {
  const isPng = type === "hide";
  const filename = isPng ? "stego.png" : "recovered.wav";
  return (
    <section className="result-panel" aria-live="polite">
      <div className="result-icon" aria-hidden="true">✓</div>
      <div className="result-copy">
        <span className="eyebrow">Operation complete</span>
        <h2>{isPng ? "Audio hidden successfully" : "Audio recovered successfully"}</h2>
        <p><strong>{filename}</strong><span>{formatBytes(blob.size)}</span></p>
      </div>
      <button className="primary-button result-button" type="button" onClick={() => downloadBlob(blob, filename)}>
        Download {isPng ? "PNG" : "WAV"} <span aria-hidden="true">↓</span>
      </button>
      <button className="secondary-button" type="button" onClick={onReset}>Start another</button>
    </section>
  );
}

function App() {
  const [mode, setMode] = useState("hide");
  const [apiStatus, setApiStatus] = useState("checking");
  const [wav, setWav] = useState(null);
  const [image, setImage] = useState(null);
  const [password, setPassword] = useState("");
  const [method, setMethod] = useState("chunk");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const imageUrl = useRef(null);

  useEffect(() => {
    let active = true;
    checkHealth().then((healthy) => active && setApiStatus(healthy ? "connected" : "unavailable"));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    return () => {
      if (imageUrl.current) URL.revokeObjectURL(imageUrl.current);
    };
  }, []);

  const selectImage = (file) => {
    if (imageUrl.current) URL.revokeObjectURL(imageUrl.current);
    imageUrl.current = file ? URL.createObjectURL(file) : null;
    setImage(file);
    setError("");
  };

  const reset = () => {
    setWav(null);
    selectImage(null);
    setPassword("");
    setError("");
    setResult(null);
  };

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const blob = mode === "hide"
        ? await hideAudio({ wav, image, password, method })
        : await recoverAudio({ image, password, method });
      setResult({ type: mode, blob });
    } catch (requestError) {
      setError(requestError.message || "The operation could not be completed.");
    } finally {
      setLoading(false);
    }
  };

  const canSubmit = Boolean(image && password && (mode === "recover" || wav)) && !loading;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <ProductMark />
          <div><strong>Audio / Image</strong><span>STEGANOGRAPHY WORKBENCH</span></div>
        </div>
        <nav className="main-nav" aria-label="Primary navigation">
          <button className={mode === "hide" ? "active" : ""} onClick={() => { setMode("hide"); setResult(null); setError(""); }} type="button">Hide Audio</button>
          <button className={mode === "recover" ? "active" : ""} onClick={() => { setMode("recover"); setResult(null); setError(""); }} type="button">Recover Audio</button>
        </nav>
        <StatusIndicator status={apiStatus} />
      </header>

      <main className="workspace">
        <div className="intro">
          <div>
            <span className="eyebrow">Secure media utility / 05</span>
            <h1>{mode === "hide" ? "Hide audio inside an image" : "Recover your original audio"}</h1>
            <p>{mode === "hide"
              ? "Encrypt a WAV file and embed it into a PNG image."
              : "Extract the encrypted payload and recover the WAV using the correct password and embedding method."}</p>
          </div>
          <div className="mode-label"><span className="mode-line" />{mode === "hide" ? "ENCODE" : "DECODE"}</div>
        </div>

        {result ? <Result type={result.type} blob={result.blob} onReset={reset} /> : (
          <form className="workspace-grid" onSubmit={submit}>
            <div className="input-column">
              {mode === "hide" && (
                <FileDrop id="wav-file" label="Audio file" hint="Required / WAV" accept=".wav,audio/wav" file={wav} onFile={(file) => { setWav(file); setError(""); }} onRemove={() => setWav(null)} />
              )}
              <FileDrop
                id="png-file"
                label={mode === "hide" ? "Cover image" : "Stego image"}
                hint="Required / PNG"
                accept=".png,image/png"
                file={image}
                onFile={selectImage}
                onRemove={() => selectImage(null)}
                preview={imageUrl.current && <img src={imageUrl.current} alt="" className="image-preview" />}
              />
            </div>
            <div className="settings-column">
              <MethodSelector method={method} onChange={setMethod} />
              <div className="field-group">
                <div className="field-heading"><label htmlFor="password">Password</label><span>Required</span></div>
                <PasswordField id="password" value={password} onChange={setPassword} />
                <p className="field-note">The same password is required to recover this audio. It is never stored.</p>
              </div>
              <div className="submit-area">
                {error && <div className="error-message" role="alert"><span>!</span>{error}</div>}
                <button className="primary-button submit-button" type="submit" disabled={!canSubmit}>
                  {loading ? <><span className="spinner" aria-hidden="true" />{mode === "hide" ? "Encrypting..." : "Recovering..."}</> : mode === "hide" ? "Encrypt & Hide Audio" : "Recover Audio"}
                  {!loading && <span aria-hidden="true">→</span>}
                </button>
                <p className="security-note"><span>▣</span> AES-256-GCM authenticated encryption</p>
              </div>
            </div>
          </form>
        )}
      </main>
      <footer className="footer"><span>LOCAL WORKBENCH</span><span>Files remain in memory and are sent only to your configured API.</span></footer>
    </div>
  );
}

export default App;
