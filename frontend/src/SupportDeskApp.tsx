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

function contactTitle(conversation: Conversation): string {
  const contact = conversation.contact;
  if (contact.username) return `@${contact.username}`;
  const fullName = [contact.first_name, contact.last_name].filter(Boolean).join(" ");
  return fullName || `MAX user ${contact.max_user_id}`;
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
    const created = await sendMessage(activeId, text.trim());
    setMessages((items) => [...items, created]);
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
                name={contactTitle(conversation)}
                info={`${conversation.status} · unread ${conversation.unread_count}`}
                active={conversation.id === activeId}
                onClick={() => setActiveId(conversation.id)}
              />
            ))}
          </ConversationList>
        </Sidebar>
        <ChatContainer>
          <ConversationHeader>
            <ConversationHeader.Content
              userName={activeConversation ? contactTitle(activeConversation) : "Chats"}
              info={activeConversation?.status || "Select conversation"}
            />
          </ConversationHeader>
          <MessageList>
            {messages.map((message) => (
              <ChatMessage
                key={message.id}
                model={{
                  message: message.text || " ",
                  sentTime: message.created_at || "",
                  sender: message.author_display,
                  direction: message.direction === "outgoing" ? "outgoing" : "incoming",
                  position: "single"
                }}
              >
                <ChatMessage.Footer
                  sender={`${message.author_display} · ${message.send_status}`}
                  sentTime={message.created_at || ""}
                />
                {message.send_status === "failed" ? (
                  <button
                    className="support-desk-retry"
                    type="button"
                    onClick={() => void handleRetry(message.id)}
                  >
                    Retry
                  </button>
                ) : null}
              </ChatMessage>
            ))}
          </MessageList>
          <MessageInput placeholder="Type message" attachButton={false} onSend={handleSend} />
        </ChatContainer>
      </MainContainer>
    </div>
  );
}
