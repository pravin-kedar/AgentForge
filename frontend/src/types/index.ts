export interface User {
  id: number;
  email: string;
  full_name: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface ChatRequest {
  conversation_id?: string | null;
  message: string;
}

export interface ChatResponse {
  conversation_id: string;
  message: string;
  tool_activity: string[];
}

export interface ConversationSummary {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface MessageItem {
  id: number;
  role: "user" | "assistant";
  content: string | null;
  created_at: string;
}

export interface ConversationDetail extends ConversationSummary {
  messages: MessageItem[];
}

/** A message as rendered in the Chat UI - includes locally-generated
 * optimistic entries that don't have a backend id yet. */
export interface ChatUIMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolActivity?: string[];
  pending?: boolean;
}
