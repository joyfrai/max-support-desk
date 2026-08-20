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
import { type ChangeEvent, type UIEvent, useEffect, useMemo, useRef, useState } from "react";
import { loadConversations, loadMessages, retryMessage, sendMessage } from "./api";
import type { Conversation, Message } from "./types";
import "./styles.css";

const CONVERSATION_PAGE_SIZE = 100;
const MOBILE_MEDIA_QUERY = "(max-width: 576px)";

type MobilePane = "chats" | "chat";

type SupportRealtimeEvent = {
  event: "message.created" | "message.status_changed";
  payload: {
    conversation_id?: number;
    message_id?: number;
  };
};

function contactDisplayName(conversation: Conversation): string {
  const contact = conversation.contact;
  const fullName = [contact.last_name, contact.first_name].filter(Boolean).join(" ");
  if (fullName) return fullName;
  if (contact.username) return `@${contact.username}`;
  return `MAX user ${contact.max_user_id}`;
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

function renderMessageContent(message: Message) {
  const hasText = message.text.trim().length > 0;
  const hasAttachments = message.attachments.length > 0;
  if (!hasAttachments) return undefined;

  return (
    <ChatMessage.CustomContent>
      {hasText ? <div className="support-desk-message-text">{message.text}</div> : null}
      <div className="support-desk-message-attachments">
        {message.attachments.map((attachment) =>
          attachment.download_url ? (
            <a
              href={attachment.download_url}
              key={attachment.id}
              target="_blank"
              rel="noreferrer"
            >
              {attachment.file_name}
            </a>
          ) : (
            <span key={attachment.id}>{attachment.file_name}</span>
          )
        )}
      </div>
    </ChatMessage.CustomContent>
  );
}

export function SupportDeskApp() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [selectedFilesByConversation, setSelectedFilesByConversation] = useState<Record<number, File[]>>({});
  const [inputTextByConversation, setInputTextByConversation] = useState<Record<number, string>>({});
  const [isCompactMobile, setIsCompactMobile] = useState(() =>
    window.matchMedia(MOBILE_MEDIA_QUERY).matches
  );
  const [mobilePane, setMobilePane] = useState<MobilePane>("chats");
  const [conversationsLoading, setConversationsLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const conversationListHostRef = useRef<HTMLDivElement | null>(null);
  const activeSearchRef = useRef(search);
  const conversationsLoadingRef = useRef(false);
  const hasMoreConversationsRef = useRef(true);
  const nextOffsetRef = useRef(0);
  const conversationRequestIdRef = useRef(0);
  const conversationReachEndLockedRef = useRef(false);
  const activeIdRef = useRef<number | null>(activeId);

  const activeConversation = useMemo(
    () => conversations.find((item) => item.id === activeId) || null,
    [activeId, conversations]
  );
  const activeFiles = activeId ? selectedFilesByConversation[activeId] || [] : [];
  const activeInputText = activeId ? inputTextByConversation[activeId] || "" : "";
  const messageInputValue = activeFiles.length > 0 && !activeInputText ? " " : activeInputText;

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
      hasMoreConversationsRef.current = page.has_more && page.conversations.length > 0;
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
    hasMoreConversationsRef.current = true;
    nextOffsetRef.current = 0;
    conversationReachEndLockedRef.current = false;
    const timer = window.setTimeout(() => {
      void loadConversationPage(search, 0, false);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    activeIdRef.current = activeId;
  }, [activeId]);

  useEffect(() => {
    const media = window.matchMedia(MOBILE_MEDIA_QUERY);
    const handleChange = () => setIsCompactMobile(media.matches);
    handleChange();
    media.addEventListener("change", handleChange);
    return () => media.removeEventListener("change", handleChange);
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

  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const root = document.getElementById("support-desk-root");
    const basePath = (root?.dataset.basePath || "").replace(/\/+$/, "");
    const socket = new WebSocket(`${protocol}//${window.location.host}${basePath}/ws/support/`);

    socket.onmessage = (event: MessageEvent<string>) => {
      let realtimeEvent: SupportRealtimeEvent;
      try {
        realtimeEvent = JSON.parse(event.data) as SupportRealtimeEvent;
      } catch {
        return;
      }

      if (!["message.created", "message.status_changed"].includes(realtimeEvent.event)) return;

      void loadConversationPage(activeSearchRef.current, 0, false);
      const conversationId = realtimeEvent.payload.conversation_id;
      if (conversationId && conversationId === activeIdRef.current) {
        loadMessages(conversationId)
          .then(setMessages)
          .catch((err: Error) => setError(err.message));
      }
    };

    socket.onerror = () => setError("Не удалось подключить живое обновление чата");
    return () => socket.close();
  }, []);

  useEffect(() => {
    const host = conversationListHostRef.current;
    const scroller = host?.querySelector(".scrollbar-container");
    if (!(scroller instanceof HTMLDivElement)) return;

    const handleScroll = () => {
      const distanceToEnd = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight;
      if (distanceToEnd > 48) {
        conversationReachEndLockedRef.current = false;
        return;
      }
      if (distanceToEnd <= 2) {
        handleConversationListReachEnd();
      }
    };

    scroller.addEventListener("scroll", handleScroll);
    return () => scroller.removeEventListener("scroll", handleScroll);
  }, [conversations.length, isCompactMobile, mobilePane]);

  async function handleSend(_: string, text: string) {
    const trimmedText = (text || activeInputText).trim();
    const filesToSend = activeFiles;
    if (!activeId || (!trimmedText && filesToSend.length === 0)) return;
    const conversationId = activeId;
    setSelectedFilesByConversation((current) => ({ ...current, [conversationId]: [] }));
    setInputTextByConversation((current) => ({ ...current, [conversationId]: "" }));
    const result = await sendMessage(activeId, trimmedText, filesToSend);
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
    if (
      conversationReachEndLockedRef.current ||
      conversationsLoadingRef.current ||
      !hasMoreConversationsRef.current
    ) {
      return;
    }
    conversationReachEndLockedRef.current = true;
    void loadConversationPage(search, nextOffsetRef.current, true);
  }

  function handleConversationListScroll(event: UIEvent<HTMLDivElement>) {
    const target = event.currentTarget;
    const distanceToEnd = target.scrollHeight - target.scrollTop - target.clientHeight;
    if (distanceToEnd > 48) {
      conversationReachEndLockedRef.current = false;
    }
  }

  function handleConversationClick(conversationId: number) {
    setActiveId(conversationId);
    if (isCompactMobile) setMobilePane("chat");
  }

  function handleFileInputChange(event: ChangeEvent<HTMLInputElement>) {
    if (activeId) {
      const files = Array.from(event.target.files || []);
      setSelectedFilesByConversation((current) => ({ ...current, [activeId]: files }));
    }
    event.target.value = "";
  }

  function handleInputChange(_: string, textContent: string) {
    if (!activeId) return;
    setInputTextByConversation((current) => ({ ...current, [activeId]: textContent.trim() ? textContent : "" }));
  }

  const showSidebar = !isCompactMobile || mobilePane === "chats";
  const showChatContainer = !isCompactMobile || mobilePane === "chat";
  const mobilePaneStyle = isCompactMobile
    ? {
        flexBasis: "100%",
        width: "100%",
        maxWidth: "100%",
        minWidth: "100%"
      }
    : undefined;

  return (
    <div className="support-desk-shell">
      {error ? <div className="support-desk-error">{error}</div> : null}
      <input
        ref={fileInputRef}
        className="support-desk-file-input"
        type="file"
        multiple
        onChange={handleFileInputChange}
      />
      <MainContainer responsive={!isCompactMobile}>
        {showSidebar ? (
          <Sidebar position="left" scrollable={false} style={mobilePaneStyle}>
            <div className="support-desk-search">
              <Search
                onChange={setSearch}
                onClearClick={() => setSearch("")}
                placeholder="Поиск по чатам"
                value={search}
              />
            </div>
            <div className="support-desk-conversation-list-host" ref={conversationListHostRef}>
              <ConversationList
                loading={conversationsLoading && conversations.length === 0}
                loadingMore={conversationsLoading && conversations.length > 0}
                onYReachEnd={handleConversationListReachEnd}
                onScroll={handleConversationListScroll}
              >
                {conversations.map((conversation) => (
                  <ChatConversation
                    key={conversation.id}
                    name={contactDisplayName(conversation)}
                    info={statusLabel(conversation.status)}
                    unreadCnt={conversation.unread_count || undefined}
                    unreadDot={conversation.unread_count > 0}
                    active={conversation.id === activeId}
                    onClick={() => handleConversationClick(conversation.id)}
                  />
                ))}
              </ConversationList>
            </div>
          </Sidebar>
        ) : null}
        {showChatContainer ? (
          <ChatContainer style={mobilePaneStyle}>
            <ConversationHeader>
              {isCompactMobile ? <ConversationHeader.Back onClick={() => setMobilePane("chats")} /> : null}
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
              {activeFiles.length > 0 ? (
                <ConversationHeader.Actions>
                  <span
                    className="support-desk-attachment-chip"
                    title={activeFiles.map((file) => file.name).join(", ")}
                  >
                    {activeFiles.length === 1 ? activeFiles[0].name : `Файлов: ${activeFiles.length}`}
                  </span>
                  <button
                    className="support-desk-clear-files"
                    type="button"
                    aria-label="Убрать выбранные файлы"
                    title="Убрать выбранные файлы"
                    onClick={() =>
                      activeId
                        ? setSelectedFilesByConversation((current) => ({ ...current, [activeId]: [] }))
                        : undefined
                    }
                  >
                    ×
                  </button>
                </ConversationHeader.Actions>
              ) : null}
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
                    position: "single",
                    type: message.attachments.length > 0 ? "custom" : "text",
                    payload: renderMessageContent(message)
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
            <MessageInput
              placeholder="Введите сообщение"
              value={messageInputValue}
              attachButton
              sendDisabled={!activeId || (!activeInputText.trim() && activeFiles.length === 0)}
              onAttachClick={() => fileInputRef.current?.click()}
              onChange={handleInputChange}
              onSend={handleSend}
            />
          </ChatContainer>
        ) : null}
      </MainContainer>
    </div>
  );
}
