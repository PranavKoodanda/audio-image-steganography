const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

async function readError(response) {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // Fall through to the status text for non-JSON responses.
  }
  return response.statusText || "The request could not be completed.";
}

async function request(path, formData) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      body: formData,
    });
  } catch {
    throw new Error("The API is unavailable. Check that the backend is running.");
  }

  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.blob();
}

export async function checkHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/health`);
    return response.ok;
  } catch {
    return false;
  }
}

export function hideAudio({ wav, image, password, method }) {
  const formData = new FormData();
  formData.append("wav", wav);
  formData.append("image", image);
  formData.append("password", password);
  formData.append("method", method);
  return request("/api/hide", formData);
}

export function recoverAudio({ image, password, method }) {
  const formData = new FormData();
  formData.append("image", image);
  formData.append("password", password);
  formData.append("method", method);
  return request("/api/recover", formData);
}
