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
  Search,
  Sidebar
} from "@chatscope/chat-ui-kit-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { loadConversations, loadMessages, retryMessage, sendMessage } from "./api";
import type { Conversation, Message } from "./types";
import "./styles.css";

const CONVERSATION_PAGE_SIZE = 100;

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
  const [search, setSearch] = useState("");
  const [conversationsLoading, setConversationsLoading] = useState(false);
  const activeSearchRef = useRef(search);
  const conversationsLoadingRef = useRef(false);
  const hasMoreConversationsRef = useRef(true);
  const nextOffsetRef = useRef(0);
  const conversationRequestIdRef = useRef(0);

  const activeConversation = useMemo(
    () => conversations.find((item) => item.id === activeId) || null,
    [activeId, conversations]
  );

  async function loadConversationPage(query: string, offset: number, append: boolean) {
    if (append && conversationsLoadingRef.current) return;
    const requestId = conversationRequestIdRef.current + 1;
    conversationRequestIdRef.current = requestId;
    conversationsLoadingRef.current = true;
    setConversationsLoading(true);
    try {
      const page = await loadConversations({
        offset,
        limit: CONVERSATION_PAGE_SIZE,
        search: query
      });
      if (requestId !== conversationRequestIdRef.current || query !== activeSearchRef.current) return;
      setConversations((current) => {
        if (!append) return page.conversations;
        const existingIds = new Set(current.map((item) => item.id));
        const nextItems = page.conversations.filter((item) => !existingIds.has(item.id));
        return [...current, ...nextItems];
      });
      nextOffsetRef.current = page.next_offset;
      hasMoreConversationsRef.current = page.has_more;
      setActiveId((current) => {
        if (append && current) return current;
        if (page.conversations.some((item) => item.id === current)) return current;
        return page.conversations[0]?.id || null;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки чатов");
    } finally {
      if (requestId === conversationRequestIdRef.current) {
        conversationsLoadingRef.current = false;
        setConversationsLoading(false);
      }
    }
  }

  useEffect(() => {
    activeSearchRef.current = search;
    const timer = window.setTimeout(() => {
      void loadConversationPage(search, 0, false);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [search]);

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

  function handleConversationListReachEnd() {
    if (conversationsLoadingRef.current || !hasMoreConversationsRef.current) return;
    void loadConversationPage(search, nextOffsetRef.current, true);
  }

  return (
    <div className="support-desk-shell">
      {error ? <div className="support-desk-error">{error}</div> : null}
      <MainContainer responsive>
        <Sidebar position="left" scrollable>
          <div className="support-desk-search">
            <Search
              onChange={setSearch}
              onClearClick={() => setSearch("")}
              placeholder="Поиск по чатам"
              value={search}
            />
          </div>
          <ConversationList
            loading={conversationsLoading && conversations.length === 0}
            loadingMore={conversationsLoading && conversations.length > 0}
            onYReachEnd={handleConversationListReachEnd}
          >
            {conversations.map((conversation) => (
              <ChatConversation
                key={conversation.id}
                name={contactDisplayName(conversation)}
                info={statusLabel(conversation.status)}
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
