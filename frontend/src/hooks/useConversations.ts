import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../services/api";
import type { ConversationDetail, ConversationSummary } from "../types";

export function useConversations() {
  return useQuery({
    queryKey: ["conversations"],
    queryFn: async () => {
      const { data } = await api.get<ConversationSummary[]>("/api/v1/conversations");
      return data;
    },
  });
}

export function useConversation(conversationId: string | null) {
  return useQuery({
    queryKey: ["conversations", conversationId],
    queryFn: async () => {
      const { data } = await api.get<ConversationDetail>(`/api/v1/conversations/${conversationId}`);
      return data;
    },
    enabled: !!conversationId,
  });
}

export function useDeleteConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (conversationId: string) => {
      await api.delete(`/api/v1/conversations/${conversationId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
}
