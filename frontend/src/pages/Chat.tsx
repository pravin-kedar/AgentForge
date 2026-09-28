import { useEffect, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import { useConversation } from "../hooks/useConversations";
import { useSendMessage } from "../hooks/useChat";
import { extractErrorMessage } from "../services/api";
import type { ChatUIMessage } from "../types";

function Bubble({ msg }: { msg: ChatUIMessage }) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className="max-w-[70%]">
        <div
          className={`whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm ${
            isUser ? "bg-brand-600 text-white" : "bg-white text-gray-800 border border-gray-200"
          }`}
        >
          {msg.pending ? <span className="italic text-gray-400">Agent is thinking...</span> : msg.content}
        </div>
        {!!msg.toolActivity?.length && (
          <div className="mt-1 text-xs text-gray-400">used: {msg.toolActivity.join(", ")}</div>
        )}
      </div>
    </div>
  );
}

export function Chat() {
  const [searchParams, setSearchParams] = useSearchParams();
  const conversationId = searchParams.get("conversation_id");

  const { data: conversation } = useConversation(conversationId);
  const sendMessage = useSendMessage();

  const [messages, setMessages] = useState<ChatUIMessage[]>([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const loadedConversationId = useRef<string | null>(null);

  useEffect(() => {
    if (conversation && loadedConversationId.current !== conversation.id) {
      setMessages(
        conversation.messages.map((m) => ({
          id: String(m.id),
          role: m.role,
          content: m.content ?? "",
        }))
      );
      loadedConversationId.current = conversation.id;
    }
    if (!conversationId) {
      setMessages([]);
      loadedConversationId.current = null;
    }
  }, [conversation, conversationId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sendMessage.isPending) return;

    setError(null);
    setInput("");
    const userMsg: ChatUIMessage = { id: `local-${Date.now()}`, role: "user", content: text };
    const placeholder: ChatUIMessage = { id: "pending", role: "assistant", content: "", pending: true };
    setMessages((prev) => [...prev, userMsg, placeholder]);

    try {
      const result = await sendMessage.mutateAsync({ conversation_id: conversationId, message: text });
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== "pending"),
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: result.message,
          toolActivity: result.tool_activity,
        },
      ]);
      if (!conversationId) {
        loadedConversationId.current = result.conversation_id;
        setSearchParams({ conversation_id: result.conversation_id });
      }
    } catch (err) {
      setMessages((prev) => prev.filter((m) => m.id !== "pending"));
      setError(extractErrorMessage(err));
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto px-6 py-4">
        {messages.length === 0 && (
          <div className="mx-auto max-w-md pt-16 text-center text-gray-400">
            <p className="text-lg font-medium text-gray-500">Plan your next trip</p>
            <p className="mt-1 text-sm">Try: "Plan a 4 day trip to Goa for me, I like beaches and outdoor activities."</p>
          </div>
        )}
        {messages.map((msg) => (
          <Bubble key={msg.id} msg={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {error && <div className="mx-6 mb-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      <form onSubmit={handleSubmit} className="flex gap-2 border-t border-gray-200 bg-white px-6 py-4">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask AgentForge to plan your trip..."
          className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
          disabled={sendMessage.isPending}
        />
        <button
          type="submit"
          disabled={sendMessage.isPending || !input.trim()}
          className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
