import { useCallback, useEffect, useRef, useState } from 'react';

export const SUPPORTED_LANGUAGES = [
  { code: 'en-IN', label: 'English', short: 'EN' },
  { code: 'ta-IN', label: 'தமிழ்', short: 'தமிழ்' },
];

export function isSpeechRecognitionSupported() {
  if (typeof window === 'undefined') return false;
  return Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
}

export function useVoiceInput({
  defaultLang = 'en-IN',
  onTranscriptChange,
} = {}) {
  const [isListening, setIsListening] = useState(false);
  const [lang, setLang] = useState(defaultLang);
  const [error, setError] = useState(null);

  const recognitionRef = useRef(null);
  const baseTextRef = useRef('');
  const isManuallyStoppedRef = useRef(false);

  const supported = isSpeechRecognitionSupported();

  const stopListening = useCallback(() => {
    isManuallyStoppedRef.current = true;
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // Ignore stop errors
      }
      recognitionRef.current = null;
    }
    setIsListening(false);
  }, []);

  const startListening = useCallback(
    (existingInputText = '') => {
      if (!supported) {
        setError('Voice input is not supported in this browser. Please use Chrome, Edge, or Safari.');
        return;
      }

      // Stop any existing instance
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // Ignore
        }
        recognitionRef.current = null;
      }

      setError(null);
      isManuallyStoppedRef.current = false;
      baseTextRef.current = existingInputText ? existingInputText.trim() : '';

      const SpeechRecognition =
        window.SpeechRecognition || window.webkitSpeechRecognition;

      const recognition = new SpeechRecognition();
      recognitionRef.current = recognition;

      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = lang;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        setIsListening(true);
        setError(null);
      };

      recognition.onresult = (event) => {
        let sessionFinal = '';
        let sessionInterim = '';

        for (let i = 0; i < event.results.length; i++) {
          const item = event.results[i];
          const textPiece = item[0]?.transcript || '';
          if (item.isFinal) {
            sessionFinal += textPiece;
          } else {
            sessionInterim += textPiece;
          }
        }

        const basePrefix = baseTextRef.current;
        const currentSpoken = (sessionFinal + (sessionInterim ? ' ' + sessionInterim : '')).trim();
        const fullPrompt = basePrefix
          ? `${basePrefix} ${currentSpoken}`
          : currentSpoken;

        if (onTranscriptChange && currentSpoken) {
          onTranscriptChange(fullPrompt);
        }
      };

      recognition.onerror = (event) => {
        const errType = event.error;
        if (errType === 'no-speech') {
          return;
        }
        if (errType === 'not-allowed') {
          setError('Microphone permission was denied. Please allow microphone access in your browser settings.');
        } else if (errType === 'audio-capture') {
          setError('No microphone found on your device.');
        } else if (errType === 'network') {
          setError('Voice recognition network error.');
        } else {
          setError(`Voice input error: ${errType}`);
        }
        setIsListening(false);
      };

      recognition.onend = () => {
        if (!isManuallyStoppedRef.current && recognitionRef.current === recognition) {
          try {
            recognition.start();
            return;
          } catch {
            // End
          }
        }
        setIsListening(false);
      };

      try {
        recognition.start();
      } catch (err) {
        setError(`Failed to start microphone: ${err.message}`);
        setIsListening(false);
      }
    },
    [supported, lang, onTranscriptChange]
  );

  const toggleListening = useCallback(
    (currentInputText = '') => {
      if (isListening) {
        stopListening();
      } else {
        startListening(currentInputText);
      }
    },
    [isListening, startListening, stopListening]
  );

  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // Ignore
        }
      }
    };
  }, []);

  return {
    isListening,
    isSupported: supported,
    lang,
    setLang,
    error,
    startListening,
    stopListening,
    toggleListening,
  };
}
