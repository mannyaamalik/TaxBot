"use client";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import { uuid } from "@/lib/utils";
import {
  ChatSession,
  Message,
  MessageStatus,
  SourceItem,
} from "@/types";

function newSession(): ChatSession {
  const now = new Date();
  return {
    id:         uuid(),
    title:      "New conversation",
    messages:   [],
    createdAt:  now,
    updatedAt:  now,
    session_id: uuid(),
  };
}

interface ChatStore {
  sessions:          ChatSession[];
  activeSid:         string;
  language:          "en" | "hi";
  calculatorOpen:    boolean;

  // Derived
  activeSession:     () => ChatSession;

  // Actions
  newChat:           () => void;
  selectSession:     (id: string) => void;
  renameSession:     (id: string, title: string) => void;
  deleteSession:     (id: string) => void;
  addUserMessage:    (content: string) => string;
  addAssistantMessage: (
    content: string,
    status: MessageStatus,
    sources: SourceItem[],
    streaming?: boolean
  ) => string;
  updateMessage:     (id: string, partial: Partial<Message>) => void;
  setLanguage:       (lang: "en" | "hi") => void;
  setCalculatorOpen: (open: boolean) => void;
}

export const useChatStore = create<ChatStore>()(
  persist(
    (set, get) => {
      const initial = newSession();

      return {
        sessions:       [initial],
        activeSid:      initial.id,
        language:       "en",
        calculatorOpen: false,

        activeSession: () =>
          get().sessions.find((s) => s.id === get().activeSid) ?? get().sessions[0],

        newChat: () => {
          const s = newSession();
          set((state) => ({
            sessions:  [s, ...state.sessions],
            activeSid: s.id,
          }));
        },

        selectSession: (id) => set({ activeSid: id }),

        renameSession: (id, title) =>
          set((state) => ({
            sessions: state.sessions.map((s) =>
              s.id === id ? { ...s, title, updatedAt: new Date() } : s
            ),
          })),

        deleteSession: (id) =>
          set((state) => {
            const remaining = state.sessions.filter((s) => s.id !== id);
            if (remaining.length === 0) {
              const s = newSession();
              return { sessions: [s], activeSid: s.id };
            }
            const activeSid =
              state.activeSid === id ? remaining[0].id : state.activeSid;
            return { sessions: remaining, activeSid };
          }),

        addUserMessage: (content) => {
          const id = uuid();
          const msg: Message = {
            id,
            role: "user",
            content,
            status: "normal",
            sources: [],
            timestamp: new Date(),
          };
          set((state) => ({
            sessions: state.sessions.map((s) =>
              s.id === state.activeSid
                ? { ...s, messages: [...s.messages, msg], updatedAt: new Date(),
                    title: s.messages.length === 0 ? content.slice(0, 50) : s.title }
                : s
            ),
          }));
          return id;
        },

        addAssistantMessage: (content, status, sources, streaming) => {
          const id = uuid();
          const msg: Message = {
            id, role: "assistant", content, status, sources,
            timestamp: new Date(), streaming,
          };
          set((state) => ({
            sessions: state.sessions.map((s) =>
              s.id === state.activeSid
                ? { ...s, messages: [...s.messages, msg], updatedAt: new Date() }
                : s
            ),
          }));
          return id;
        },

        updateMessage: (id, partial) =>
          set((state) => ({
            sessions: state.sessions.map((s) =>
              s.id === state.activeSid
                ? {
                    ...s,
                    messages: s.messages.map((m) =>
                      m.id === id ? { ...m, ...partial } : m
                    ),
                  }
                : s
            ),
          })),

        setLanguage:       (language)       => set({ language }),
        setCalculatorOpen: (calculatorOpen) => set({ calculatorOpen }),
      };
    },
    {
      name: "taxmitra-chat",
      partialize: (s) => ({
        sessions:  s.sessions,
        activeSid: s.activeSid,
        language:  s.language,
      }),
    }
  )
);
