export type Contact = {
  id: number;
  max_user_id: string;
  username: string;
  first_name: string;
  last_name: string;
};

export type Conversation = {
  id: number;
  contact: Contact;
  status: string;
  assigned_to_id: number | null;
  last_message_id: number | null;
  last_message_at: string | null;
  unread_count: number;
};

export type Message = {
  id: number;
  conversation_id: number;
  direction: "incoming" | "outgoing";
  author_display: string;
  text: string;
  send_status: string;
  created_at: string | null;
  attachments: MessageAttachment[];
};

export type MessageAttachment = {
  id: number;
  file_name: string;
  mime_type: string;
  size_bytes: number | null;
  download_url: string;
};

export type SendMessageResult = {
  message: Message;
  conversation: Conversation;
};

export type ConversationPage = {
  conversations: Conversation[];
  offset: number;
  limit: number;
  next_offset: number;
  has_more: boolean;
};
