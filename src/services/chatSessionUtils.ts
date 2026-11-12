export function buildNewConversation(
  conversationId: string,
  mode = 'daily',
  now = new Date().toISOString(),
) {
  return {
    id: conversationId,
    title: '新对话',
    mode,
    createdAt: now,
    updatedAt: now,
    updated_at: now,
    archived: false,
  }
}

export type ChatSessionLike = {
  id: string
  title?: string
  archived?: boolean
}

export function filterVisibleSessions(
  sessions: ChatSessionLike[],
  searchQuery: string,
  showArchived: boolean,
) {
  const base = sessions.filter((s) => showArchived || !s.archived)
  if (!searchQuery) return base
  return base.filter((s) => String(s.title || '').includes(searchQuery))
}

export function buildUiStatePayload(draft: string, scrollTop: number) {
  return {
    draft,
    scrollTop,
    updatedAt: new Date().toISOString(),
  }
}
