import { ChatRequest, ChatResponse } from "@/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** POST /chat — returns a full ChatResponse. */
export async function sendChat(req: ChatRequest): Promise<ChatResponse> {
  const res = await fetch(`${BASE}/chat`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify(req),
  });

  if (res.status === 429) {
    throw new Error("RATE_LIMITED");
  }
  if (!res.ok) {
    throw new Error(`HTTP_${res.status}`);
  }
  return res.json() as Promise<ChatResponse>;
}

/**
 * POST /chat/stream — SSE streaming endpoint.
 * Falls back to sendChat() if the endpoint returns 404 (backend not upgraded yet).
 *
 * Calls onToken(chunk) for each streamed token and onDone(response) when complete.
 */
export async function sendChatStream(
  req:     ChatRequest,
  onToken: (chunk: string) => void,
  onDone:  (response: ChatResponse) => void,
  signal?: AbortSignal
): Promise<void> {
  // Try streaming first
  const res = await fetch(`${BASE}/chat/stream`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify(req),
    signal,
  }).catch(() => null);

  if (!res || !res.ok || !res.body) {
    // Fall back to regular endpoint
    const data = await sendChat(req);
    // Simulate token-by-token for perceived streaming
    const words = data.answer.split(" ");
    for (const word of words) {
      onToken(word + " ");
      await new Promise((r) => setTimeout(r, 12));
    }
    onDone(data);
    return;
  }

  const reader  = res.body.getReader();
  const decoder = new TextDecoder();
  let   buffer  = "";
  let   finalResponse: ChatResponse | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const raw = line.slice(6).trim();
      if (raw === "[DONE]") break;
      try {
        const event = JSON.parse(raw) as { token?: string; done?: boolean; response?: ChatResponse };
        if (event.token) onToken(event.token);
        if (event.done && event.response) finalResponse = event.response;
      } catch {
        // non-JSON line — skip
      }
    }
  }

  if (finalResponse) onDone(finalResponse);
}

/** GET /health */
export async function getHealth() {
  const res = await fetch(`${BASE}/health`);
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}
