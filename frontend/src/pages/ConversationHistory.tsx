import { useNavigate } from "react-router-dom";

import { useConversations, useDeleteConversation } from "../hooks/useConversations";

export function ConversationHistory() {
  const { data: conversations, isLoading } = useConversations();
  const deleteConversation = useDeleteConversation();
  const navigate = useNavigate();

  return (
    <div className="mx-auto h-full max-w-2xl overflow-y-auto px-6 py-8">
      <h1 className="mb-6 text-xl font-semibold text-gray-800">Conversation History</h1>

      {isLoading && <p className="text-sm text-gray-400">Loading...</p>}
      {!isLoading && conversations?.length === 0 && (
        <p className="text-sm text-gray-400">No conversations yet - start one from the Chat tab.</p>
      )}

      <ul className="space-y-2">
        {conversations?.map((c) => (
          <li
            key={c.id}
            className="flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-3 hover:border-brand-300"
          >
            <button
              className="flex-1 text-left"
              onClick={() => navigate(`/chat?conversation_id=${c.id}`)}
            >
              <div className="text-sm font-medium text-gray-800">{c.title || `Conversation ${c.id.slice(0, 8)}`}</div>
              <div className="text-xs text-gray-400">Updated {new Date(c.updated_at).toLocaleString()}</div>
            </button>
            <button
              onClick={() => deleteConversation.mutate(c.id)}
              className="ml-3 rounded-md px-2 py-1 text-xs text-red-500 hover:bg-red-50"
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
