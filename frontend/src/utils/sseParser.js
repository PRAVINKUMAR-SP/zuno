/**
 * Robust SSE (Server-Sent Events) parser for Zuno chat streaming.
 * Handles split network chunks, multiline data, keepalive comments, and UTF-8 characters.
 */
export function createSSEParser(onEvent) {
  let buffer = '';

  const parseBlock = (block) => {
    if (!block || !block.trim()) return;

    let eventType = 'message';
    const dataLines = [];

    const lines = block.split(/\r?\n/);
    for (const rawLine of lines) {
      if (!rawLine || rawLine.startsWith(':')) {
        // Comment or heartbeat line (: keepalive)
        continue;
      }
      if (rawLine.startsWith('event:')) {
        eventType = rawLine.slice(6).trim();
      } else if (rawLine.startsWith('data:')) {
        dataLines.push(rawLine.slice(5).replace(/^ /, ''));
      }
    }

    if (dataLines.length === 0) return;

    const rawData = dataLines.join('\n');
    let parsedData = rawData;
    try {
      parsedData = JSON.parse(rawData);
    } catch {
      // Keep as string if not valid JSON
    }

    // Standardize eventType: use explicit event: header or fallback to data.type
    const resolvedType =
      eventType !== 'message'
        ? eventType
        : (parsedData && typeof parsedData === 'object' && parsedData.type) || 'message';

    if (onEvent) {
      try {
        onEvent({
          type: resolvedType,
          data: parsedData,
          raw: rawData,
        });
      } catch (err) {
        console.error('[SSEParser] Error in event handler:', err);
      }
    }
  };

  return {
    push(chunk) {
      if (!chunk) return;
      buffer += chunk;
      const parts = buffer.split(/\r?\n\r?\n/);
      buffer = parts.pop() ?? '';
      for (const block of parts) {
        if (block.trim()) {
          parseBlock(block);
        }
      }
    },
    finish() {
      if (buffer.trim()) {
        const remaining = buffer.split(/\r?\n\r?\n/);
        buffer = '';
        for (const block of remaining) {
          if (block.trim()) {
            parseBlock(block);
          }
        }
      }
    },
    reset() {
      buffer = '';
    },
  };
}

