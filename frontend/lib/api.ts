export type Decision = "APPROVED" | "DENIED" | "ESCALATED" | "NEEDS_INFO";

export type TraceEvent = {
  id: number;
  conversation_id: string;
  step: string;
  title: string;
  detail: Record<string, unknown>;
  severity: string;
  created_at: string;
};

export type ChatResponse = {
  conversation_id: string;
  assistant_message: string;
  decision: Decision;
  triggered_rules: string[];
  needs_escalation: boolean;
  injection_detected: boolean;
  trace: TraceEvent[];
};

export type ConversationSummary = {
  id: string;
  customer_email: string | null;
  status: string;
  latest_message: string;
  created_at: string;
  updated_at: string;
  decision: Decision | null;
};

export type Health = {
  status: string;
  database: string;
  llm_provider: string;
  provider_configured: boolean;
  business_today: string;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function eventUrl(conversationId: string) {
  return `${API_BASE_URL}/api/conversations/${conversationId}/events`;
}

export async function postChat(input: { conversation_id: string; message: string; customer_email?: string }) {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }

  return (await response.json()) as ChatResponse;
}

export async function getConversations() {
  const response = await fetch(`${API_BASE_URL}/api/conversations`, { cache: "no-store" });
  if (!response.ok) {
    return [] as ConversationSummary[];
  }
  return (await response.json()) as ConversationSummary[];
}

export async function getHealth() {
  const response = await fetch(`${API_BASE_URL}/api/health`, { cache: "no-store" });
  if (!response.ok) {
    return null;
  }
  return (await response.json()) as Health;
}

