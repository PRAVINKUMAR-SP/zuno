import { useEffect, useRef, useState } from 'react';
import {
  AlertCircle,
  ArrowUp,
  FileText,
  Globe,
  Menu,
  Paperclip,
  Sparkles,
  Square,
  X,
} from 'lucide-react';
import Sidebar from './components/Sidebar';
import MessageBubble from './components/MessageBubble';
import ZunoLogo from './components/ZunoLogo';
import {
  deleteConversation,
  deleteDoc,
  getHealth,
  getMessages,
  listConversations,
  renameConversation,
  streamChat,
  uploadDoc,
} from './api/zunoApi';

export default function App() {
  const [conversations, setConversations] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const mode = 'auto';
  const [useWeb, setUseWeb] = useState(null); // null = auto-detect, true = always web search
  const [pendingDocs, setPendingDocs] = useState([]);
  const [uploadingDoc, setUploadingDoc] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState('');

  const abortRef = useRef(null);
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);
  const tokenBufferRef = useRef('');
  const flushTimerRef = useRef(null);
  const streamMetaRef = useRef({ botId: null, firstTokenMs: null });

  const refreshConversations = async () => {
    try {
      const list = await listConversations();
      setConversations(list || []);
    } catch {
      // Handled by health check
    }
  };

  const refreshHealth = async () => {
    try {
      const h = await getHealth();
      setHealth(h);
    } catch {
      setHealth({ status: 'offline', database: 'disconnected', ai: { ready: false } });
    }
  };

  useEffect(() => {
    refreshHealth();
    refreshConversations();
    const timer = setInterval(refreshHealth, 12000);
    return () => clearInterval(timer);
  }, []);

  const handleUploadFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setError('');
    setUploadingDoc(true);
    try {
      const uploaded = await uploadDoc(file);
      setPendingDocs((prev) => [
        ...prev.filter((d) => d.id !== uploaded.id && d.name !== uploaded.name),
        uploaded,
      ]);
    } catch (err) {
      setError(`Document upload failed: ${err.message}`);
    } finally {
      setUploadingDoc(false);
    }
  };

  const handleRemoveDoc = async (docId) => {
    try {
      await deleteDoc(docId);
      setPendingDocs((prev) => prev.filter((d) => d.id !== docId));
    } catch (err) {
      setError(`Remove document failed: ${err.message}`);
    }
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: isStreaming ? 'auto' : 'smooth' });
  }, [messages, isStreaming]);

  const handleSelectConversation = async (id) => {
    setError('');
    setActiveId(id);
    setPendingDocs([]);
    setSidebarOpen(false);
    try {
      const data = await getMessages(id);
      setMessages(data || []);
    } catch (err) {
      setError(`Could not load chat: ${err.message}`);
    }
  };

  const handleNewChat = () => {
    if (isStreaming) return;
    setActiveId(null);
    setMessages([]);
    setPendingDocs([]);
    setError('');
    setSidebarOpen(false);
    textareaRef.current?.focus();
  };

  const handleRename = async (id, title) => {
    try {
      const updated = await renameConversation(id, title);
      setConversations((prev) => prev.map((c) => (c.id === id ? updated : c)));
    } catch (err) {
      setError(`Rename failed: ${err.message}`);
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeId === id) {
        setActiveId(null);
        setMessages([]);
      }
    } catch (err) {
      setError(`Delete failed: ${err.message}`);
    }
  };

  const flushTokenBuffer = () => {
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
          ? { ...m, content: m.content + buffered, firstTokenMs: m.firstTokenMs ?? firstTokenMs }
          : m
      )
    );
  };

  const handleStop = () => {
    flushTokenBuffer();
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
  };

  const sendMessage = async (textOverride) => {
    const promptText = (textOverride ?? input).trim();
    if (!promptText || isStreaming) return;

    const outgoingAttachments = pendingDocs.map(({ id, name }) => ({ id, name }));
    setError('');
    setInput('');
    setPendingDocs([]);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

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
      { id: tempUserId, role: 'user', content: promptText, attachments: outgoingAttachments },
      { id: tempBotId, role: 'assistant', content: '', mode },
    ]);

    const startedAt = performance.now();
    let firstTokenMs = null;
    const controller = new AbortController();
    abortRef.current = controller;
    setIsStreaming(true);

    try {
      await streamChat({
        conversationId: activeId,
        message: promptText,
        mode,
        useWeb,
        attachments: outgoingAttachments,
        signal: controller.signal,
        onMeta: (meta) => {
          if (meta.conversationId && meta.conversationId !== activeId) {
            setActiveId(meta.conversationId);
          }
          refreshConversations();
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
                    sources: doneEvt.sources || [],
                  }
                : m
            )
          );
          refreshConversations();
        },
        onError: (err) => {
          flushTokenBuffer();
          setError(err.message);
        },
      });
    } catch (err) {
      flushTokenBuffer();
      if (err.name !== 'AbortError') {
        setError(err.message || 'Failed to get response from Zuno backend.');
        setMessages((prev) => prev.filter((m) => m.id !== tempBotId || m.content));
      }
    } finally {
      if (flushTimerRef.current) {
        clearTimeout(flushTimerRef.current);
        flushTimerRef.current = null;
      }
      tokenBufferRef.current = '';
      abortRef.current = null;
      setIsStreaming(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleInputResize = (e) => {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 180)}px`;
  };

  return (
    <div className="flex h-screen overflow-hidden bg-[#0b0c10] text-zinc-100">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={handleSelectConversation}
        onNewChat={handleNewChat}
        onRename={handleRename}
        onDelete={handleDelete}
        health={health}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <main className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-13 shrink-0 items-center justify-between border-b border-white/[0.06] bg-[#0b0c10]/85 px-4 backdrop-blur-md">
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              className="rounded-lg p-1.5 text-zinc-400 hover:bg-white/[0.06] hover:text-white md:hidden"
              aria-label="Open sidebar"
            >
              <Menu className="h-5 w-5" />
            </button>
            <span className="text-sm font-medium text-zinc-200">Zuno</span>
            <span className="rounded-md border border-white/[0.09] bg-white/[0.03] px-2 py-0.5 text-[11px] text-zinc-400">
              Qwen3-4B
            </span>
          </div>
        </header>

        {error && (
          <div className="mx-auto mt-3 flex w-full max-w-3xl items-center gap-2 rounded-xl border border-rose-500/25 bg-rose-500/10 px-4 py-2.5 text-xs text-rose-200">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
            <span className="flex-1">{error}</span>
          </div>
        )}

        <div className="flex-1 overflow-y-auto px-4 pt-6 pb-4">
          {messages.length === 0 ? (
            <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center text-center">
              <div className="mb-4">
                <ZunoLogo size={48} />
              </div>
              <h2 className="text-2xl font-semibold tracking-tight text-zinc-100">
                What can I help you with today?
              </h2>
            </div>
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-6 pb-4">
              {messages.map((msg, idx) => (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  isStreaming={isStreaming && idx === messages.length - 1 && msg.role === 'assistant'}
                />
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <footer className="shrink-0 bg-gradient-to-t from-[#0b0c10] via-[#0b0c10] to-transparent px-4 pt-2 pb-4">
          <div className="mx-auto max-w-3xl">
            {pendingDocs.length > 0 && (
              <div className="mb-2 flex flex-wrap items-center gap-1.5 px-1">
                {pendingDocs.map((doc) => (
                  <span
                    key={doc.id}
                    className="inline-flex items-center gap-1.5 rounded-full border border-white/[0.09] bg-[#15161d] px-2.5 py-1 text-[11px] text-zinc-300"
                    title={`${doc.chunkCount} indexed chunks`}
                  >
                    <FileText className="h-3 w-3 text-emerald-400" />
                    <span className="max-w-44 truncate">{doc.name}</span>
                    <button
                      type="button"
                      onClick={() => handleRemoveDoc(doc.id)}
                      className="rounded-full p-0.5 text-zinc-500 transition hover:bg-white/[0.08] hover:text-zinc-200"
                      aria-label={`Remove ${doc.name}`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}

            <div className="rounded-[22px] border border-white/[0.11] bg-[#15161d] px-4 pt-3 pb-2.5 shadow-[0_8px_30px_rgba(0,0,0,0.45)] transition focus-within:border-white/25">
              <textarea
                ref={textareaRef}
                rows={1}
                value={input}
                onChange={handleInputResize}
                onKeyDown={handleKeyDown}
                placeholder="Ask Zuno anything..."
                className="max-h-44 w-full resize-none bg-transparent text-[15px] leading-relaxed text-zinc-100 placeholder-zinc-500 outline-none"
              />

              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,.md,.pdf,.csv,.json,.java,.py,.js,.jsx,.ts,.tsx,.sql,.xml,.yml,.yaml,.properties"
                onChange={handleUploadFile}
                className="hidden"
              />

              <div className="mt-2.5 flex items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-1.5">
                  <div
                    className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-medium text-emerald-300"
                    title="Adaptive Response Engine: automatically picks Greeting, Simple, Detailed, Coding, or Debugging format"
                  >
                    <Sparkles className="h-3 w-3" />
                    <span>Adaptive</span>
                    <span className="text-emerald-300/60">· Auto</span>
                  </div>

                  <button
                    type="button"
                    onClick={() => setUseWeb((prev) => (prev === true ? null : true))}
                    className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium transition ${
                      useWeb === true
                        ? 'border-sky-500/35 bg-sky-500/15 text-sky-300'
                        : 'border-white/[0.08] bg-white/[0.03] text-zinc-400 hover:border-white/15 hover:text-zinc-200'
                    }`}
                    title="Web search is automatic for current topics; click to force Web Search on"
                  >
                    <Globe className="h-3 w-3" />
                    <span>{useWeb === true ? 'Web · On' : 'Web · Auto'}</span>
                  </button>

                  <button
                    type="button"
                    disabled={uploadingDoc}
                    onClick={() => fileInputRef.current?.click()}
                    className="inline-flex items-center gap-1.5 rounded-full border border-white/[0.08] bg-white/[0.03] px-2.5 py-1 text-[11px] font-medium text-zinc-400 transition hover:border-white/15 hover:text-zinc-200 disabled:opacity-50"
                    title="Upload a document (PDF, TXT, MD, CSV, JSON, code) for local RAG"
                  >
                    <Paperclip className="h-3 w-3" />
                    <span>{uploadingDoc ? 'Indexing...' : 'Attach doc'}</span>
                  </button>
                </div>

                <div className="flex items-center gap-2.5">
                  <span className="hidden text-[11px] text-zinc-600 sm:inline">
                    Enter to send · Shift+Enter newline
                  </span>

                  {isStreaming ? (
                    <button
                      type="button"
                      onClick={handleStop}
                      className="flex h-8 w-8 items-center justify-center rounded-full bg-zinc-200 text-zinc-900 transition hover:bg-white"
                      title="Stop generating"
                    >
                      <Square className="h-3.5 w-3.5 fill-current" />
                    </button>
                  ) : (
                    <button
                      type="button"
                      disabled={!input.trim()}
                      onClick={() => sendMessage()}
                      className="flex h-8 w-8 items-center justify-center rounded-full bg-zinc-100 text-zinc-950 transition hover:bg-white disabled:cursor-not-allowed disabled:bg-white/[0.08] disabled:text-zinc-600"
                      title="Send message"
                    >
                      <ArrowUp className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </footer>
      </main>
    </div>
  );
}
