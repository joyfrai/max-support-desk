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
};

export type SendMessageResult = {
  message: Message;
  conversation: Conversation;
};
