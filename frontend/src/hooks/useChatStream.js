import { useCallback, useRef, useState } from 'react';
import { streamChat } from '../api/zunoApi';

/**
 * Custom hook to manage real-time chat streaming, token batching (40ms), and cancellation.
 */
export function useChatStream({ onConversationCreated } = {}) {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeMessageId, setActiveMessageId] = useState(null);
  const [error, setError] = useState('');
  const [sources, setSources] = useState([]);

  const abortRef = useRef(null);
  const tokenBufferRef = useRef('');
  const flushTimerRef = useRef(null);
  const streamMetaRef = useRef({ botId: null, firstTokenMs: null });

  const flushTokenBuffer = useCallback(() => {
    if (flushTimerRef.current) {
      clearTimeout(flushTimerRef.current);
      flushTimerRef.current = null;
    }
    const buffered = tokenBufferRef.current;
    const { botId, firstTokenMs } = streamMetaRef.current;
    if (!buffered || !botId) return;

    tokenBufferRef.current = '';
    setMessages((prev) =>
      prev.map((m) =>
        m.id === botId
          ? {
              ...m,
              content: (m.content || '') + buffered,
              firstTokenMs: m.firstTokenMs ?? firstTokenMs,
            }
          : m
      )
    );
  }, []);

  const stopGeneration = useCallback(() => {
    flushTokenBuffer();
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setIsStreaming(false);
    setActiveMessageId(null);
  }, [flushTokenBuffer]);

  const clearStream = useCallback(() => {
    stopGeneration();
    setMessages([]);
    setError('');
    setSources([]);
    setActiveMessageId(null);
  }, [stopGeneration]);

  const sendMessage = useCallback(
    async ({
      conversationId,
      message,
      mode = 'auto',
      useWeb = null,
      attachments = [],
    }) => {
      const promptText = (message || '').trim();
      if (!promptText || isStreaming) return;

      stopGeneration();
      setError('');
      setSources([]);

      const tempUserId = `user-${Date.now()}`;
      const tempBotId = `bot-${Date.now() + 1}`;

      tokenBufferRef.current = '';
      if (flushTimerRef.current) {
        clearTimeout(flushTimerRef.current);
        flushTimerRef.current = null;
      }
      streamMetaRef.current = { botId: tempBotId, firstTokenMs: null };

      setMessages((prev) => [
        ...prev,
        {
          id: tempUserId,
          role: 'user',
          content: promptText,
          attachments,
        },
        {
          id: tempBotId,
          role: 'assistant',
          content: '',
          mode,
          sources: [],
        },
      ]);

      const startedAt = performance.now();
      let firstTokenMs = null;
      const controller = new AbortController();
      abortRef.current = controller;
      setIsStreaming(true);
      setActiveMessageId(tempBotId);

      try {
        await streamChat({
          conversationId,
          message: promptText,
          mode,
          useWeb,
          attachments,
          signal: controller.signal,
          onMeta: (meta) => {
            if (meta?.conversationId && onConversationCreated) {
              onConversationCreated(meta.conversationId);
            }
          },
          onSources: (incomingSources) => {
            if (Array.isArray(incomingSources) && incomingSources.length > 0) {
              setSources(incomingSources);
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === tempBotId ? { ...m, sources: incomingSources } : m
                )
              );
            }
          },
          onToken: (delta) => {
            if (!delta || controller.signal.aborted) return;
            if (firstTokenMs === null) {
              firstTokenMs = Math.round(performance.now() - startedAt);
              streamMetaRef.current.firstTokenMs = firstTokenMs;
            }
            tokenBufferRef.current += delta;
            if (!flushTimerRef.current) {
              flushTimerRef.current = setTimeout(flushTokenBuffer, 40);
            }
          },
          onDone: (doneEvt) => {
            flushTokenBuffer();
            setMessages((prev) =>
              prev.map((m) =>
                m.id === tempBotId
                  ? {
                      ...m,
                      id: doneEvt.messageId || tempBotId,
                      content: doneEvt.content || m.content,
                      responseTimeMs: doneEvt.elapsedMs,
                      firstTokenMs: firstTokenMs ?? m.firstTokenMs,
                      mode: doneEvt.mode || mode,
                      toolsUsed: doneEvt.toolsUsed || [],
                      sources: doneEvt.sources || m.sources || [],
                    }
                  : m
              )
            );
            setIsStreaming(false);
            setActiveMessageId(null);
            abortRef.current = null;
          },
          onError: (err) => {
            flushTokenBuffer();
            if (!controller.signal.aborted) {
              setError(err.message || 'Stream connection failed');
            }
            setIsStreaming(false);
            setActiveMessageId(null);
            abortRef.current = null;
          },
        });
      } catch (err) {
        flushTokenBuffer();
        if (!controller.signal.aborted) {
          setError(err.message || 'Error occurred while streaming response');
        }
        setIsStreaming(false);
        setActiveMessageId(null);
        abortRef.current = null;
      }
    },
    [isStreaming, onConversationCreated, stopGeneration, flushTokenBuffer]
  );

  const retryMessage = useCallback(
    (index) => {
      if (isStreaming) return;
      const targetUserMsg =
        index !== undefined
          ? messages[index]
          : [...messages].reverse().find((m) => m.role === 'user');
      if (targetUserMsg && targetUserMsg.content) {
        sendMessage({
          message: targetUserMsg.content,
          attachments: targetUserMsg.attachments || [],
        });
      }
    },
    [isStreaming, messages, sendMessage]
  );

  return {
    messages,
    setMessages,
    isStreaming,
    activeMessageId,
    error,
    setError,
    sources,
    sendMessage,
    stopGeneration,
    retryMessage,
    clearStream,
  };
}

