import { useEffect, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import { Markdown } from "../components/Markdown";
import { useConversation } from "../hooks/useConversations";
import { useSendMessage } from "../hooks/useChat";
import { extractErrorMessage } from "../services/api";
import type { ChatUIMessage } from "../types";

const TOOL_LABELS: Record<string, { icon: string; label: string }> = {
  search_hotels: { icon: "🏨", label: "Searched hotels" },
  get_hotel_details: { icon: "🛏️", label: "Hotel details" },
  check_hotel_availability: { icon: "📅", label: "Checked availability" },
  get_destination_info: { icon: "🗺️", label: "Destination info" },
  search_activities: { icon: "🏄", label: "Found activities" },
  get_weather: { icon: "🌤️", label: "Checked weather" },
  create_trip: { icon: "✈️", label: "Saved trip" },
  get_my_trips: { icon: "🧳", label: "Your trips" },
  get_trip: { icon: "🧳", label: "Trip details" },
  update_trip: { icon: "✏️", label: "Updated trip" },
  delete_trip: { icon: "🗑️", label: "Deleted trip" },
};

function ToolChips({ tools }: { tools: string[] }) {
  const unique = [...new Set(tools)];
  return (
    <div className="mb-2 flex flex-wrap gap-1.5">
      {unique.map((name) => {
        const meta = TOOL_LABELS[name] ?? { icon: "🔧", label: name };
        return (
          <span
            key={name}
            className="inline-flex items-center gap-1 rounded-full border border-brand-100 bg-brand-50 px-2.5 py-0.5 text-xs font-medium text-brand-700"
          >
            <span aria-hidden>{meta.icon}</span>
            {meta.label}
          </span>
        );
      })}
    </div>
  );
}

function ThinkingDots() {
  return (
    <div className="flex items-center gap-2 text-sm text-gray-400">
      <span className="flex gap-1">
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="h-2 w-2 animate-bounce rounded-full bg-brand-500"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </span>
      Planning your trip...
    </div>
  );
}

function Bubble({ msg }: { msg: ChatUIMessage }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-gradient-to-br from-brand-500 to-brand-700 px-4 py-2.5 text-sm text-white shadow-sm">
          {msg.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-indigo-600 text-sm text-white shadow-sm">
        ✈
      </div>
      <div className="min-w-0 max-w-[85%] rounded-2xl rounded-tl-md border border-gray-200 bg-white px-5 py-4 shadow-sm">
        {msg.pending ? (
          <ThinkingDots />
        ) : (
          <>
            {!!msg.toolActivity?.length && <ToolChips tools={msg.toolActivity} />}
            <Markdown content={msg.content} />
          </>
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
