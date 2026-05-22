import type { Conversation, ConversationPage, Message, SendMessageResult } from "./types";

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
    throw new Error(`Ошибка запроса: ${response.status}`);
  }
  return (await response.json()) as T;
}

async function requestFormJson<T>(url: string, body: FormData): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "X-CSRFToken": csrfToken()
    },
    body
  });
  if (!response.ok) {
    throw new Error(`Ошибка запроса: ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function loadConversations(params: {
  offset?: number;
  limit?: number;
  search?: string;
} = {}): Promise<ConversationPage> {
  const query = new URLSearchParams();
  query.set("offset", String(params.offset ?? 0));
  query.set("limit", String(params.limit ?? 100));
  if (params.search?.trim()) query.set("search", params.search.trim());
  return requestJson<ConversationPage>(`/api/conversations/?${query.toString()}`);
}

export async function loadMessages(conversationId: number): Promise<Message[]> {
  const payload = await requestJson<{ messages: Message[] }>(
    `/api/conversations/${conversationId}/messages/?limit=200`
  );
  return payload.messages;
}

export async function sendMessage(
  conversationId: number,
  text: string,
  files: File[] = []
): Promise<SendMessageResult> {
  if (files.length > 0) {
    const form = new FormData();
    form.set("text", text);
    files.forEach((file) => form.append("files", file));
    return requestFormJson<SendMessageResult>(`/api/conversations/${conversationId}/messages/`, form);
  }
  return requestJson<SendMessageResult>(
    `/api/conversations/${conversationId}/messages/`,
    {
      method: "POST",
      body: JSON.stringify({ text })
    }
  );
}

export async function retryMessage(messageId: number): Promise<Message> {
  const payload = await requestJson<{ message: Message }>(`/api/messages/${messageId}/retry/`, {
    method: "POST"
  });
  return payload.message;
}
