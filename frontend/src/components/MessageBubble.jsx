import { memo, useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Check, Clock, Copy, FileText, Volume2, VolumeX } from 'lucide-react';
import ZunoLogo from './ZunoLogo';
import { isSpeechSynthesisSupported, speakText, stopSpeaking } from '../utils/speechUtils';
import '../styles/streaming.css';

function prepareStreamingMarkdown(text, isStreaming) {
  if (!isStreaming || !text) return text;
  const fenceMatches = text.match(/```/g);
  if (fenceMatches && fenceMatches.length % 2 === 1) {
    return `${text}\n\`\`\``;
  }
  return text;
}

function CodeBlock({ className, children, ...props }) {
  const [copied, setCopied] = useState(false);
  const match = /language-(\w+)/.exec(className || '');
  const codeText = String(children).replace(/\n$/, '');

  if (!match && !codeText.includes('\n')) {
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  }

  const handleCopy = async () => {
    await navigator.clipboard.writeText(codeText);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="my-3 overflow-hidden rounded-xl border border-white/[0.09] bg-[#08090d]">
      <div className="flex items-center justify-between border-b border-white/[0.07] bg-white/[0.03] px-3.5 py-1.5 text-[11px] text-zinc-400">
        <span className="font-mono">{match ? match[1] : 'code'}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1 rounded-md px-2 py-0.5 text-zinc-300 transition hover:bg-white/[0.08] hover:text-white"
        >
          {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className="overflow-x-auto p-3.5 text-[13px] leading-relaxed text-zinc-200">
        <code className={className} {...props}>
          {children}
        </code>
      </pre>
    </div>
  );
}

function stripInlineMarkdown(line) {
  const codeSpans = [];
  let text = line.replace(/`([^`]+)`/g, (_, code) => {
    const token = `\u0000CODE${codeSpans.length}\u0000`;
    codeSpans.push(code);
    return token;
  });

  text = text
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1 ($2)')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
    .replace(/(^|\s)\*([^*\s][^*]*?)\*(?=\s|[.,!?;:)]|$)/g, '$1$2')
    .replace(/(^|\s)_([^_\s][^_]*?)_(?=\s|[.,!?;:)]|$)/g, '$1$2')
    .replace(/~~([^~]+)~~/g, '$1');

  return text.replace(/\u0000CODE(\d+)\u0000/g, (_, idx) => codeSpans[Number(idx)] ?? '');
}

function toPlainCopyText(markdown) {
  if (!markdown) return '';
  const blocks = markdown.replace(/\r\n/g, '\n').split(/(```[\s\S]*?```)/g);

  return blocks
    .map((block) => {
      if (block.startsWith('```') && block.endsWith('```')) {
        return block.replace(/^```[^\n]*\n?/, '').replace(/\n?```$/, '').trimEnd();
      }
      return block
        .split('\n')
        .map((line) => {
          if (/^\s*([-*_])\1{2,}\s*$/.test(line)) return '';
          let cleaned = line
            .replace(/^\s{0,3}#{1,6}\s+/, '')
            .replace(/^\s*>\s?/, '')
            .replace(/^(\s*)[-*+]\s+/, '$1• ');
          return stripInlineMarkdown(cleaned);
        })
        .join('\n');
    })
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

const MessageBubble = memo(function MessageBubble({ message, isStreaming }) {
  const [copiedMsg, setCopiedMsg] = useState(false);
  const [isSpeakingThis, setIsSpeakingThis] = useState(false);
  const isUser = message.role === 'user';
  const hasTTS = isSpeechSynthesisSupported();

  useEffect(() => {
    return () => {
      if (isSpeakingThis) {
        stopSpeaking();
      }
    };
  }, [isSpeakingThis]);

  const toggleSpeech = () => {
    if (isSpeakingThis) {
      stopSpeaking();
      setIsSpeakingThis(false);
    } else {
      speakText(
        message.content,
        'en-IN',
        () => setIsSpeakingThis(true),
        () => setIsSpeakingThis(false),
        () => setIsSpeakingThis(false)
      );
    }
  };

  const elapsedSec =
    typeof message.responseTimeMs === 'number' && message.responseTimeMs > 0
      ? (message.responseTimeMs / 1000).toFixed(2)
      : null;
  const firstTokenSec =
    typeof message.firstTokenMs === 'number' && message.firstTokenMs > 0
      ? (message.firstTokenMs / 1000).toFixed(2)
      : null;

  const copyResponse = async () => {
    if (!message.content) return;
    await navigator.clipboard.writeText(toPlainCopyText(message.content));
    setCopiedMsg(true);
    setTimeout(() => setCopiedMsg(false), 1500);
  };

  if (isUser) {
    const attachments = Array.isArray(message.attachments) ? message.attachments : [];
    return (
      <div className="zuno-msg-enter flex w-full flex-col items-end gap-1.5">
        {attachments.length > 0 && (
          <div className="flex flex-wrap justify-end gap-1.5">
            {attachments.map((att, idx) => (
              <span
                key={`${att.id || att.name}-${idx}`}
                className="inline-flex items-center gap-1.5 rounded-xl border border-white/[0.09] bg-[#171921] px-2.5 py-1 text-xs text-zinc-300"
              >
                <FileText className="h-3.5 w-3.5 text-emerald-400" />
                <span className="max-w-52 truncate">{att.name}</span>
              </span>
            ))}
          </div>
        )}
        <div className="max-w-[80%] rounded-2xl rounded-tr-sm border border-white/[0.08] bg-[#20222b] px-4 py-2.5 text-[15px] leading-relaxed text-zinc-100 sm:max-w-[72%]">
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="zuno-msg-enter group flex w-full items-start gap-3.5">
      <div className={`mt-0.5 shrink-0 ${isStreaming ? 'zuno-logo-active' : ''}`}>
        <ZunoLogo size={26} />
      </div>

      <div className="min-w-0 flex-1 pt-0.5">
        <div className={`zuno-prose break-words ${isStreaming && message.content ? 'streaming-cursor' : ''}`}>
          {message.content ? (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{ code: CodeBlock }}
            >
              {prepareStreamingMarkdown(message.content, isStreaming)}
            </ReactMarkdown>
          ) : (
            <div className="inline-flex items-center gap-2.5 py-1 text-sm">
              <span className="inline-flex h-3.5 items-end gap-0.5" aria-hidden="true">
                <span className="zuno-wave-bar h-3 w-0.5 rounded-full bg-emerald-400" style={{ animationDelay: '0ms' }} />
                <span className="zuno-wave-bar h-3.5 w-0.5 rounded-full bg-emerald-300" style={{ animationDelay: '160ms' }} />
                <span className="zuno-wave-bar h-2.5 w-0.5 rounded-full bg-teal-400" style={{ animationDelay: '320ms' }} />
              </span>
              <span className="zuno-think-shimmer font-medium tracking-wide">
                Thinking
              </span>
            </div>
          )}
        </div>

        {isStreaming && message.content && (
          <div className="mt-2 inline-flex items-center gap-2 text-xs text-zinc-400">
            <span className="inline-flex h-3 items-end gap-0.5" aria-hidden="true">
              <span className="zuno-wave-bar h-2.5 w-0.5 rounded-full bg-emerald-400" style={{ animationDelay: '0ms' }} />
              <span className="zuno-wave-bar h-3 w-0.5 rounded-full bg-emerald-300" style={{ animationDelay: '160ms' }} />
              <span className="zuno-wave-bar h-2 w-0.5 rounded-full bg-teal-400" style={{ animationDelay: '320ms' }} />
            </span>
            <span className="zuno-think-shimmer font-medium">Generating response...</span>
          </div>
        )}

        {!isStreaming && message.content && (
          <div className="zuno-msg-enter mt-2.5 flex flex-wrap items-center gap-2.5 text-[11px] text-zinc-500">
            <button
              type="button"
              onClick={copyResponse}
              className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-zinc-400 transition hover:bg-white/[0.06] hover:text-zinc-200"
              title="Copy response"
            >
              {copiedMsg ? (
                <Check className="h-3 w-3 text-emerald-400" />
              ) : (
                <Copy className="h-3 w-3" />
              )}
              <span>{copiedMsg ? 'Copied' : 'Copy'}</span>
            </button>

            {hasTTS && (
              <button
                type="button"
                onClick={toggleSpeech}
                className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 transition ${
                  isSpeakingThis
                    ? 'bg-emerald-500/15 text-emerald-300'
                    : 'text-zinc-400 hover:bg-white/[0.06] hover:text-zinc-200'
                }`}
                title={isSpeakingThis ? 'Stop speaking' : 'Read response aloud'}
              >
                {isSpeakingThis ? (
                  <VolumeX className="h-3 w-3 text-emerald-400" />
                ) : (
                  <Volume2 className="h-3 w-3" />
                )}
                <span>{isSpeakingThis ? 'Stop' : 'Listen'}</span>
              </button>
            )}

            {firstTokenSec && (
              <span
                className={`inline-flex items-center gap-1 font-medium ${
                  Number(firstTokenSec) <= 5.0 ? 'text-emerald-400' : 'text-amber-300'
                }`}
              >
                <Clock className="h-3 w-3" />
                {firstTokenSec}s start
              </span>
            )}

            {elapsedSec && (
              <span className="inline-flex items-center gap-1 text-zinc-500">
                {!firstTokenSec && <Clock className="h-3 w-3 text-emerald-400" />}
                {firstTokenSec ? `· ${elapsedSec}s total` : `${elapsedSec}s`}
              </span>
            )}

            {message.mode && (
              <span className="rounded border border-white/[0.08] bg-white/[0.03] px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-zinc-400">
                {message.mode === 'auto' ? 'Adaptive' : message.mode}
              </span>
            )}

            {Array.isArray(message.toolsUsed) && message.toolsUsed.map((tool) => (
              <span
                key={tool}
                className="rounded border border-sky-500/20 bg-sky-500/10 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-sky-300"
              >
                {tool}
              </span>
            ))}

            {Array.isArray(message.sources) && message.sources.length > 0 && (
              <div className="mt-1 flex w-full flex-wrap items-center gap-1.5">
                {message.sources.map((src, idx) =>
                  src.url ? (
                    <a
                      key={`${src.title}-${idx}`}
                      href={src.url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-md border border-white/[0.07] bg-white/[0.02] px-2 py-0.5 text-[10px] text-zinc-400 transition hover:border-white/20 hover:text-zinc-200"
                    >
                      {src.title}
                    </a>
                  ) : (
                    <span
                      key={`${src.title}-${idx}`}
                      className="rounded-md border border-white/[0.07] bg-white/[0.02] px-2 py-0.5 text-[10px] text-zinc-400"
                    >
                      {src.title}
                    </span>
                  )
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
});

export default MessageBubble;
