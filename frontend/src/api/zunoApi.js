import { createSSEParser } from '../utils/sseParser';

const API_BASE = '/api';

async function requestJson(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
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
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/docs`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Upload failed (${res.status})`);
  }
  return res.json();
}

export function deleteDoc(docId) {
  return requestJson(`/docs/${docId}`, { method: 'DELETE' });
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
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
    } else if (type === 'done') {
      if (onDone) onDone(payload);
    } else if (type === 'error') {
      if (onError) onError(new Error(payload.message || 'Stream error'));
    }
  });

  try {
    while (true) {
      if (signal?.aborted) {
        await reader.cancel().catch(() => {});
        break;
      }

      const { done, value } = await reader.read();
      if (done) {
        parser.push(decoder.decode());
        parser.finish();
        break;
      }

      parser.push(decoder.decode(value, { stream: true }));
    }
  } finally {
    if (signal?.aborted) {
      await reader.cancel().catch(() => {});
    }
  }
}

