"use client";
import { useCallback, useEffect, useRef, useState } from "react";

// Extend Window for browsers that prefix the API
declare global {
  interface Window {
    SpeechRecognition?: new () => SpeechRecognitionInstance;
    webkitSpeechRecognition?: new () => SpeechRecognitionInstance;
  }

  interface SpeechRecognitionInstance extends EventTarget {
    continuous:     boolean;
    interimResults: boolean;
    lang:           string;
    start():        void;
    stop():         void;
    onresult:       ((e: SpeechRecognitionResultEvent) => void) | null;
    onend:          (() => void) | null;
  }

  interface SpeechRecognitionResultEvent extends Event {
    results: SpeechRecognitionResultList;
  }
}

export function useVoiceInput(onResult: (text: string) => void) {
  const [listening, setListening] = useState(false);
  const [supported, setSupported] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);

  useEffect(() => {
    const SR = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    setSupported(!!SR);
    if (!SR) return;
    const rec = new SR();
    rec.continuous = false;
    rec.interimResults = false;
    rec.lang = "en-IN";
    rec.onresult = (e: SpeechRecognitionResultEvent) => {
      const text = e.results[0]?.[0]?.transcript ?? "";
      if (text) onResult(text);
    };
    rec.onend = () => setListening(false);
    recognitionRef.current = rec;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggle = useCallback(() => {
    const rec = recognitionRef.current;
    if (!rec) return;
    if (listening) { rec.stop(); setListening(false); }
    else           { rec.start(); setListening(true);  }
  }, [listening]);

  return { listening, supported, toggle };
}
