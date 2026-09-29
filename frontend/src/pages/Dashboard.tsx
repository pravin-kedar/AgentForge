import { useNavigate } from "react-router-dom";

import { useAuth } from "../hooks/useAuth";
import { useConversations } from "../hooks/useConversations";

export function Dashboard() {
  const { user } = useAuth();
  const { data: conversations } = useConversations();
  const navigate = useNavigate();

  return (
    <div className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="text-2xl font-semibold text-gray-800">
        Welcome{user?.full_name ? `, ${user.full_name}` : ""}
      </h1>
      <p className="mt-1 text-gray-500">
        You have {conversations?.length ?? 0} saved conversation{conversations?.length === 1 ? "" : "s"}.
      </p>

      <button
        onClick={() => navigate("/chat")}
        className="mt-6 rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
      >
        Start a new trip
      </button>
    </div>
  );
}
