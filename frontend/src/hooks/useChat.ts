import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "../services/api";
import type { ChatRequest, ChatResponse } from "../types";

export function useSendMessage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ChatRequest) => {
      const { data } = await api.post<ChatResponse>("/api/v1/chat", payload);
      return data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      queryClient.invalidateQueries({ queryKey: ["conversations", data.conversation_id] });
    },
  });
}
