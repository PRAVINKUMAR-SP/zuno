/**
 * Speech Recognition and Speech Synthesis utilities for Zuno.
 */

export const SUPPORTED_LANGUAGES = [
  { code: 'en-IN', label: 'English (IN)', short: 'EN' },
  { code: 'ta-IN', label: 'தமிழ் (Tamil)', short: 'தமிழ்' },
  { code: 'en-US', label: 'English (US)', short: 'US' },
];

export function isSpeechRecognitionSupported() {
  if (typeof window === 'undefined') return false;
  return Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
}

export function isSpeechSynthesisSupported() {
  if (typeof window === 'undefined') return false;
  return 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
}

/**
 * Strips markdown symbols, code blocks, links, and formatting so the AI response
 * can be spoken clearly by TTS without reading syntax symbols.
 */
export function stripMarkdownForSpeech(markdown) {
  if (!markdown) return '';
  return markdown
    // Remove fenced code blocks completely (do not read raw code aloud)
    .replace(/```[\s\S]*?```/g, ' [code omitted] ')
    // Remove inline code
    .replace(/`([^`]+)`/g, '$1')
    // Remove markdown links, keep anchor text
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    // Remove bold and italics
    .replace(/[*_]{1,3}([^*_]+)[*_]{1,3}/g, '$1')
    // Remove header markers
    .replace(/^#{1,6}\s+/gm, '')
    // Remove bullet points / blockquotes
    .replace(/^\s*[-*+]\s+/gm, '')
    .replace(/^\s*>\s?/gm, '')
    // Remove HTML tags
    .replace(/<[^>]+>/g, '')
    // Collapse excess whitespace
    .replace(/\s+/g, ' ')
    .trim();
}

let activeUtterance = null;

export function speakText(text, lang = 'en-IN', onStart, onEnd, onError) {
  if (!isSpeechSynthesisSupported()) {
    onError?.('Speech synthesis not supported on this browser.');
    return;
  }

  stopSpeaking();

  const cleanText = stripMarkdownForSpeech(text);
  if (!cleanText) return;

  const utterance = new SpeechSynthesisUtterance(cleanText);
  activeUtterance = utterance;

  // Detect Tamil script vs English
  const isTamil = /[\u0B80-\u0BFF]/.test(cleanText);
  utterance.lang = isTamil ? 'ta-IN' : lang;
  utterance.rate = 1.0;
  utterance.pitch = 1.0;

  // Match optimal system voice if available
  const voices = window.speechSynthesis.getVoices();
  if (voices && voices.length > 0) {
    const targetLangPrefix = utterance.lang.split('-')[0];
    const matchingVoice =
      voices.find((v) => v.lang === utterance.lang) ||
      voices.find((v) => v.lang.startsWith(targetLangPrefix));
    if (matchingVoice) {
      utterance.voice = matchingVoice;
    }
  }

  utterance.onstart = () => {
    onStart?.();
  };

  utterance.onend = () => {
    activeUtterance = null;
    onEnd?.();
  };

  utterance.onerror = (e) => {
    activeUtterance = null;
    if (e.error !== 'canceled' && e.error !== 'interrupted') {
      onError?.(e.error || 'TTS error');
    }
    onEnd?.();
  };

  window.speechSynthesis.speak(utterance);
}

export function stopSpeaking() {
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    try {
      window.speechSynthesis.cancel();
    } catch {
      // Ignore cancellation exceptions
    }
  }
  activeUtterance = null;
}

export function isSpeaking() {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return false;
  return window.speechSynthesis.speaking;
}
