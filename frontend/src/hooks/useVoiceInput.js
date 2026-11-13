import { useCallback, useEffect, useRef, useState } from 'react';
import { isSpeechRecognitionSupported } from '../utils/speechUtils';

export function useVoiceInput({
  defaultLang = 'en-IN',
  onTranscriptChange,
  onSpeechEnd,
} = {}) {
  const [isListening, setIsListening] = useState(false);
  const [lang, setLang] = useState(defaultLang);
  const [error, setError] = useState(null);
  const [interimTranscript, setInterimTranscript] = useState('');

  const recognitionRef = useRef(null);
  const isManuallyStoppedRef = useRef(false);
  const finalTranscriptRef = useRef('');
  const timeoutRef = useRef(null);

  const supported = isSpeechRecognitionSupported();

  const cleanupRecognition = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch {
        // Ignore abort errors
      }
      recognitionRef.current = null;
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  const stopListening = useCallback(() => {
    isManuallyStoppedRef.current = true;
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // Ignore stop errors
      }
    }
    setIsListening(false);
    setInterimTranscript('');
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    if (finalTranscriptRef.current && onSpeechEnd) {
      onSpeechEnd(finalTranscriptRef.current.trim());
    }
  }, [onSpeechEnd]);

  const startListening = useCallback(
    (initialText = '') => {
      if (!supported) {
        setError('Voice input is not supported in this browser. Please use Chrome, Edge, or Safari.');
        return;
      }

      cleanupRecognition();
      setError(null);
      isManuallyStoppedRef.current = false;
      finalTranscriptRef.current = initialText ? initialText.trim() + ' ' : '';
      setInterimTranscript('');

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
        let currentInterim = '';
        let newlyFinal = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const item = event.results[i];
          const transcriptPiece = item[0]?.transcript || '';
          if (item.isFinal) {
            newlyFinal += transcriptPiece;
          } else {
            currentInterim += transcriptPiece;
          }
        }

        if (newlyFinal) {
          finalTranscriptRef.current += newlyFinal;
        }

        setInterimTranscript(currentInterim);

        const combinedText = (finalTranscriptRef.current + currentInterim).trim();
        if (onTranscriptChange) {
          onTranscriptChange(combinedText);
        }

        // Reset silence timer: if user speaks and pauses for 3.5s, signal speech pause
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current);
        }
        timeoutRef.current = setTimeout(() => {
          if (!isManuallyStoppedRef.current && finalTranscriptRef.current) {
            // Silence detected after speech
            setInterimTranscript('');
          }
        }, 3500);
      };

      recognition.onerror = (event) => {
        const errType = event.error;
        if (errType === 'no-speech') {
          // Normal silence, don't show alarming error
          return;
        }
        if (errType === 'not-allowed') {
          setError('Microphone permission was denied. Please allow microphone access in your browser settings.');
        } else if (errType === 'audio-capture') {
          setError('No microphone found on your device.');
        } else if (errType === 'network') {
          setError('Voice recognition network connection error.');
        } else {
          setError(`Voice input error: ${errType}`);
        }
        setIsListening(false);
      };

      recognition.onend = () => {
        // If not explicitly stopped by the user, and no fatal error, restart to keep continuous listening
        if (!isManuallyStoppedRef.current && recognitionRef.current === recognition) {
          try {
            recognition.start();
            return;
          } catch {
            // Fall through to end
          }
        }
        setIsListening(false);
        setInterimTranscript('');
      };

      try {
        recognition.start();
      } catch (err) {
        setError(`Failed to start microphone: ${err.message}`);
        setIsListening(false);
      }
    },
    [supported, cleanupRecognition, lang, onTranscriptChange, onSpeechEnd]
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

  const resetTranscript = useCallback(() => {
    finalTranscriptRef.current = '';
    setInterimTranscript('');
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanupRecognition();
    };
  }, [cleanupRecognition]);

  return {
    isListening,
    isSupported: supported,
    lang,
    setLang,
    error,
    interimTranscript,
    startListening,
    stopListening,
    toggleListening,
    resetTranscript,
  };
}
