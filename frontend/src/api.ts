import type { Conversation, Message } from "./types";

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

async function requestJson<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken(),
      ...(options.headers || {})
    },
    ...options
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function loadConversations(): Promise<Conversation[]> {
  const payload = await requestJson<{ conversations: Conversation[] }>("/api/conversations/");
  return payload.conversations;
}

export async function loadMessages(conversationId: number): Promise<Message[]> {
  const payload = await requestJson<{ messages: Message[] }>(
    `/api/conversations/${conversationId}/messages/`
  );
  return payload.messages;
}

export async function sendMessage(conversationId: number, text: string): Promise<Message> {
  const payload = await requestJson<{ message: Message }>(
    `/api/conversations/${conversationId}/messages/`,
    {
      method: "POST",
      body: JSON.stringify({ text })
    }
  );
  return payload.message;
}

export async function retryMessage(messageId: number): Promise<Message> {
  const payload = await requestJson<{ message: Message }>(`/api/messages/${messageId}/retry/`, {
    method: "POST"
  });
  return payload.message;
}

