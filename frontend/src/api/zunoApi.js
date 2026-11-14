import { createSSEParser } from '../utils/sseParser';

const API_BASE = '/api';

export function getAuthToken() {
  return localStorage.getItem('zero_auth_token');
}

export function setAuthSession(token, user) {
  if (token) localStorage.setItem('zero_auth_token', token);
  if (user) localStorage.setItem('zero_auth_user', JSON.stringify(user));
}

export function clearAuthSession() {
  localStorage.removeItem('zero_auth_token');
  localStorage.removeItem('zero_auth_user');
}

export function getStoredUser() {
  try {
    const raw = localStorage.getItem('zero_auth_user');
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

async function requestJson(path, options = {}) {
  const token = getAuthToken();
  const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders, ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    let message = text;
    try {
      const parsed = JSON.parse(text);
      if (parsed && typeof parsed === 'object') {
        message = parsed.error || parsed.message || text;
      }
    } catch {
      // Keep raw text if not JSON
    }
    throw new Error(message || `HTTP ${res.status}`);
  }
  if (res.status === 204 || res.headers.get('content-length') === '0') {
    return null;
  }
  const contentType = res.headers.get('content-type') || '';
  return contentType.includes('application/json') ? res.json() : null;
}

export function getHealth() {
  return requestJson('/health');
}

export function listConversations() {
  return requestJson('/conversations');
}

export function createConversation(title = 'New Chat') {
  return requestJson('/conversations', {
    method: 'POST',
    body: JSON.stringify({ title }),
  });
}

export function renameConversation(id, title) {
  return requestJson(`/conversations/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  });
}

export function deleteConversation(id) {
  return requestJson(`/conversations/${id}`, { method: 'DELETE' });
}

export function getMessages(conversationId) {
  return requestJson(`/conversations/${conversationId}/messages`);
}

export function listDocs() {
  return requestJson('/docs');
}

export async function uploadDoc(file) {
  const token = getAuthToken();
  const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/docs`, {
    method: 'POST',
    headers: authHeaders,
    body: form,
  });
  if (!res.ok) {
    const text = await res.text();
    let message = text;
    try {
      const parsed = JSON.parse(text);
      if (parsed && typeof parsed === 'object') {
        message = parsed.error || parsed.message || text;
      }
    } catch {
      // Keep raw text if not JSON
    }
    throw new Error(message || `HTTP ${res.status}`);
  }
  return res.json();
}

export function deleteDoc(docId) {
  return requestJson(`/docs/${docId}`, { method: 'DELETE' });
}

export function listMemories() {
  return requestJson('/memories');
}

export function deleteMemory(id) {
  return requestJson(`/memories/${id}`, { method: 'DELETE' });
}

// Authentication APIs
export function registerUser(name, email, password) {
  return requestJson('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ name, email, password }),
  });
}

export function loginUser(email, password) {
  return requestJson('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export function getProfile() {
  return requestJson('/auth/me');
}

// Admin APIs
export function getAdminUsers() {
  return requestJson('/admin/users');
}

export function updateUserLimit(userId, tokenLimit) {
  return requestJson(`/admin/users/${userId}/limit`, {
    method: 'PATCH',
    body: JSON.stringify({ tokenLimit }),
  });
}

export async function streamChat({
  conversationId,
  message,
  mode,
  useWeb,
  attachments,
  signal,
  onMeta,
  onToken,
  onSources,
  onVisualStatus,
  onVisualReady,
  onVisualError,
  onDone,
  onError,
}) {
  const body = { conversationId, message, mode };
  if (typeof useWeb === 'boolean') {
    body.useWeb = useWeb;
  }
  if (Array.isArray(attachments) && attachments.length > 0) {
    body.attachments = attachments;
  }

  const token = getAuthToken();
  const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};

  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok || !res.body) {
    const errText = await res.text().catch(() => '');
    if (res.status >= 500 && !errText.trim()) {
      throw new Error('Spring Boot backend is offline on port 8081. Start the backend with your MySQL password.');
    }
    throw new Error(errText || `HTTP ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');

  const parser = createSSEParser((event) => {
    const { type, data } = event;
    const payload = typeof data === 'object' && data !== null ? data : {};

    if (type === 'meta') {
      if (onMeta) onMeta(payload);
    } else if (type === 'token') {
      const text = payload.content !== undefined ? payload.content : (payload.text !== undefined ? payload.text : '');
      if (onToken) onToken(text);
    } else if (type === 'sources') {
      const srcList = Array.isArray(payload.sources) ? payload.sources : (Array.isArray(payload) ? payload : []);
      if (onSources) onSources(srcList);
    } else if (type === 'visual_status') {
      if (onVisualStatus) onVisualStatus(payload);
    } else if (type === 'visual_ready') {
      if (onVisualReady) onVisualReady(payload);
    } else if (type === 'visual_error') {
      if (onVisualError) onVisualError(payload);
    } else if (type === 'done') {
      if (onDone) onDone(payload);
    } else if (type === 'error') {
      if (onError) onError(new Error(payload.message || 'Stream error'));
    }
  });

  try {
    while (true) {
      if (signal?.aborted) {
        await reader.cancel().catch(() => { });
        break;
      }

      const { done, value } = await reader.read();
      if (done) {
        parser.push(decoder.decode());
        break;
      }
      parser.push(decoder.decode(value, { stream: true }));
    }
  } catch (err) {
    if (signal?.aborted) return;
    throw err;
  }
}
