import "@chatscope/chat-ui-kit-styles/dist/default/styles.min.css";
import {
  ChatContainer,
  Conversation as ChatConversation,
  ConversationHeader,
  ConversationList,
  MainContainer,
  Message as ChatMessage,
  MessageInput,
  MessageList,
  Sidebar
} from "@chatscope/chat-ui-kit-react";
import { useEffect, useMemo, useState } from "react";
import { loadConversations, loadMessages, retryMessage, sendMessage } from "./api";
import type { Conversation, Message } from "./types";
import "./styles.css";

function contactDisplayName(conversation: Conversation): string {
  const contact = conversation.contact;
  const fullName = [contact.last_name, contact.first_name].filter(Boolean).join(" ");
  if (fullName) return fullName;
  if (contact.username) return `@${contact.username}`;
  return fullName || `MAX user ${contact.max_user_id}`;
}

function contactNickname(conversation: Conversation): string {
  return conversation.contact.username ? `@${conversation.contact.username}` : "";
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    new: "Новый",
    open: "Открыт",
    pending: "Ожидает",
    closed: "Закрыт"
  };
  return labels[status] || status;
}

function sendStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    not_applicable: "",
    queued: "В очереди",
    sending: "Отправляется",
    sent: "Отправлено",
    failed: "Ошибка отправки"
  };
  return labels[status] ?? status;
}

function unreadLabel(count: number): string {
  if (count <= 0) return "нет непрочитанных";
  if (count === 1) return "1 непрочитанное";
  return `${count} непрочитанных`;
}

function formatDateTime(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  })
    .format(date)
    .replace(",", "");
}

export function SupportDeskApp() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState("");

  const activeConversation = useMemo(
    () => conversations.find((item) => item.id === activeId) || null,
    [activeId, conversations]
  );

  useEffect(() => {
    loadConversations()
      .then((items) => {
        setConversations(items);
        setActiveId((current) => current || items[0]?.id || null);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!activeId) {
      setMessages([]);
      return;
    }
    loadMessages(activeId)
      .then(setMessages)
      .catch((err: Error) => setError(err.message));
  }, [activeId]);

  async function handleSend(_: string, text: string) {
    if (!activeId || !text.trim()) return;
    const result = await sendMessage(activeId, text.trim());
    setMessages((items) => [...items, result.message]);
    setConversations((items) =>
      items.map((item) => (item.id === result.conversation.id ? result.conversation : item))
    );
  }

  async function handleRetry(messageId: number) {
    const updated = await retryMessage(messageId);
    setMessages((items) => items.map((item) => (item.id === messageId ? updated : item)));
  }

  return (
    <div className="support-desk-shell">
      {error ? <div className="support-desk-error">{error}</div> : null}
      <MainContainer responsive>
        <Sidebar position="left" scrollable>
          <ConversationList>
            {conversations.map((conversation) => (
              <ChatConversation
                key={conversation.id}
                name={contactDisplayName(conversation)}
                info={`${statusLabel(conversation.status)} · ${unreadLabel(conversation.unread_count)}`}
                unreadCnt={conversation.unread_count || undefined}
                unreadDot={conversation.unread_count > 0}
                active={conversation.id === activeId}
                onClick={() => setActiveId(conversation.id)}
              />
            ))}
          </ConversationList>
        </Sidebar>
        <ChatContainer>
          <ConversationHeader>
            <ConversationHeader.Content
              userName={activeConversation ? contactDisplayName(activeConversation) : "Чаты"}
              info={
                activeConversation
                  ? [statusLabel(activeConversation.status), contactNickname(activeConversation)]
                      .filter(Boolean)
                      .join(" · ")
                  : "Выберите чат"
              }
            />
          </ConversationHeader>
          <MessageList>
            {messages.map((message) => (
              <ChatMessage
                key={message.id}
                model={{
                  message: message.text || " ",
                  sentTime: formatDateTime(message.created_at),
                  sender: message.author_display,
                  direction: message.direction === "outgoing" ? "outgoing" : "incoming",
                  position: "single"
                }}
              >
                <ChatMessage.Footer
                  sender={[message.author_display, sendStatusLabel(message.send_status)]
                    .filter(Boolean)
                    .join(" · ")}
                  sentTime={formatDateTime(message.created_at)}
                />
                {message.send_status === "failed" ? (
                  <button
                    className="support-desk-retry"
                    type="button"
                    onClick={() => void handleRetry(message.id)}
                  >
                    Повторить
                  </button>
                ) : null}
              </ChatMessage>
            ))}
          </MessageList>
          <MessageInput placeholder="Введите сообщение" attachButton={false} onSend={handleSend} />
        </ChatContainer>
      </MainContainer>
    </div>
  );
}
