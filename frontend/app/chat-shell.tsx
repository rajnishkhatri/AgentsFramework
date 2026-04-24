/**
 * Chat shell — client component that wires Composer, StreamingMarkdown,
 * RunControls, ThreadSidebar, and ThemeToggle into a working chat UI.
 *
 * This is a placeholder integration: messages are stored in local state
 * and sent to the BFF `/api/run/stream` endpoint. The full AG-UI / CopilotKit
 * integration lands in later sprints.
 */

"use client";

import * as React from "react";
import Link from "next/link";
import { Composer } from "@/components/chat/Composer";
import { StreamingMarkdown } from "@/components/chat/StreamingMarkdown";
import { ThemeToggle } from "@/components/chat/ThemeToggle";

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
}

export function ChatShell(props: { userEmail: string }): React.JSX.Element {
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [busy, setBusy] = React.useState(false);
  const bottomRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(body: string): Promise<void> {
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      text: body,
    };
    setMessages((prev) => [...prev, userMsg]);
    setBusy(true);

    try {
      const res = await fetch("/api/run/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input: { messages: [{ role: "user", content: body }] } }),
      });

      if (!res.ok || !res.body) {
        const assistantMsg: Message = {
          id: crypto.randomUUID(),
          role: "assistant",
          text: `Error: ${res.status} — ${res.statusText}. The backend runtime is not connected yet.`,
        };
        setMessages((prev) => [...prev, assistantMsg]);
        return;
      }

      const assistantId = crypto.randomUUID();
      setMessages((prev) => [...prev, { id: assistantId, role: "assistant", text: "" }]);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let assistantText = "";

      const flushEvent = (rawEvent: string): void => {
        let eventName = "message";
        const dataLines: string[] = [];
        for (const line of rawEvent.split("\n")) {
          if (line.startsWith("event:")) {
            eventName = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            dataLines.push(line.slice(5).trimStart());
          }
        }
        if (dataLines.length === 0) return;
        const dataStr = dataLines.join("\n");
        if (eventName === "done" || dataStr === "[DONE]") return;

        try {
          const payload = JSON.parse(dataStr) as {
            type?: string;
            delta?: string;
            message?: string;
          };
          if (eventName === "TEXT_MESSAGE_CONTENT" && typeof payload.delta === "string") {
            assistantText += payload.delta;
            const snapshot = assistantText;
            setMessages((prev) =>
              prev.map((m) => (m.id === assistantId ? { ...m, text: snapshot } : m)),
            );
          } else if (eventName === "RUN_ERROR" && payload.message) {
            assistantText += `\n\n_Error: ${payload.message}_`;
            const snapshot = assistantText;
            setMessages((prev) =>
              prev.map((m) => (m.id === assistantId ? { ...m, text: snapshot } : m)),
            );
          }
        } catch {
          // Non-JSON data line — ignore.
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let sepIdx: number;
        while ((sepIdx = buffer.indexOf("\n\n")) !== -1) {
          const rawEvent = buffer.slice(0, sepIdx);
          buffer = buffer.slice(sepIdx + 2);
          if (rawEvent.trim().length > 0) flushEvent(rawEvent);
        }
      }
      if (buffer.trim().length > 0) flushEvent(buffer);
    } catch {
      const errMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        text: "Connection error — make sure the backend is running.",
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-dvh grid grid-rows-[auto_1fr_auto]">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-border-light">
        <h1 className="text-lg font-semibold m-0">ReAct Agent</h1>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted">{props.userEmail}</span>
          <ThemeToggle />
          <Link
            href="/api/auth/sign-out"
            className="text-sm text-muted hover:text-fg no-underline"
          >
            Sign out
          </Link>
        </div>
      </header>

      {/* Messages area */}
      <main className="overflow-y-auto p-4">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted text-center">
            <div className="grid gap-2">
              <p className="text-2xl m-0">What can I help you with?</p>
              <p className="text-sm m-0">Send a message to start a conversation.</p>
            </div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto grid gap-4">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={
                  msg.role === "user"
                    ? "justify-self-end bg-accent text-white rounded-lg px-4 py-2 max-w-[80%]"
                    : "justify-self-start max-w-[80%]"
                }
              >
                {msg.role === "assistant" ? (
                  <StreamingMarkdown text={msg.text} />
                ) : (
                  <span className="whitespace-pre-wrap">{msg.text}</span>
                )}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </main>

      {/* Composer */}
      <div className="max-w-3xl mx-auto w-full">
        <Composer onSend={handleSend} busy={busy} />
      </div>
    </div>
  );
}
