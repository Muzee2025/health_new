<script setup>
import { computed, ref } from 'vue'
import {
  ElButton,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElInput,
  vLoading,
} from 'element-plus'

const props = defineProps({
  sessions: { type: Array, default: () => [] },
  currentSessionId: { type: [String, Number], default: null },
  loadingSessions: { type: Boolean, default: false },
  currentMode: { type: String, default: 'daily' },
})

const emit = defineEmits(['create', 'select', 'rename', 'delete'])

const searchQuery = ref('')

const filteredSessions = computed(() => {
  const base = props.sessions.filter((session) => !session.archived)
  if (!searchQuery.value) return base
  return base.filter((session) => session.title.includes(searchQuery.value))
})

const formatSessionTime = (time) => {
  if (!time) return '--:--'
  const date = new Date(time)
  return `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

const handleSessionCommand = (command, session) => {
  if (command === 'rename') emit('rename', session)
  if (command === 'delete') emit('delete', session)
}
</script>

<template>
  <aside class="session-panel">
    <div class="session-toolbar">
      <ElButton
        type="primary"
        plain
        class="new-conv-btn"
        @click="emit('create', props.currentMode)"
      >
        <LibraryIcon name="add" /> 新对话
      </ElButton>
    </div>
    <div class="session-search">
      <ElInput v-model="searchQuery" placeholder="搜索聊天记录..." />
    </div>
    <div class="session-list" v-loading="props.loadingSessions">
      <div
        v-for="session in filteredSessions"
        :key="session.id"
        :class="['session-item', props.currentSessionId === session.id ? 'active' : '']"
        role="button"
        tabindex="0"
        :aria-current="props.currentSessionId === session.id ? 'true' : undefined"
        @click="emit('select', session.id)"
        @keydown.enter.stop.prevent="emit('select', session.id)"
        @keydown.space.stop.prevent="emit('select', session.id)"
      >
        <div class="session-top">
          <span
            class="session-mode-dot"
            :class="session.mode === 'daily' ? 'dot-daily' : 'dot-counsel'"
          />
          <span class="session-name">{{ session.title }}</span>
          <span v-if="session.archived" class="session-archived">已归档</span>
          <span class="session-time">{{ formatSessionTime(session.updated_at) }}</span>
          <ElDropdown @command="(command) => handleSessionCommand(command, session)">
            <span class="session-more" @click.stop>•••</span>
            <template #dropdown>
              <ElDropdownMenu>
                <ElDropdownItem command="rename">重命名</ElDropdownItem>
                <ElDropdownItem command="delete" divided>删除</ElDropdownItem>
              </ElDropdownMenu>
            </template>
          </ElDropdown>
        </div>
        <div class="session-preview">
          {{ session.mode === 'daily' ? '日常聊天会话' : '心理咨询会话' }}
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.session-panel {
  width: 280px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
}

.session-search {
  padding: 14px;
}

.session-toolbar {
  padding: 12px 14px 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.new-conv-btn {
  width: 110px;
}

.session-search :deep(.el-input__wrapper) {
  border-radius: var(--radius);
  box-shadow: none;
  border: 1px solid var(--border);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 10px 10px;
}

.session-item {
  padding: 16px 12px;
  border-radius: var(--radius);
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.session-item:hover {
  background: var(--surface-subtle);
}

.session-item:focus-visible {
  outline: 3px solid var(--focus-ring);
  outline-offset: 2px;
}

.session-item.active {
  background: var(--brand-50);
}

.session-top {
  display: flex;
  align-items: center;
  gap: 8px;
}

.session-archived {
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--surface-subtle);
  border-radius: 999px;
  padding: 1px 6px;
}

.session-more {
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
  padding: 0 4px;
}

.session-mode-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.dot-daily {
  background: var(--primary);
}

.dot-counsel {
  background: var(--success-text);
}

.session-name {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-time {
  font-size: 12px;
  color: var(--text-secondary);
}

.session-preview {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

@media (max-width: 980px) {
  .session-panel {
    width: 100%;
  }
}

@media (max-width: 600px) {
  .session-panel {
    max-height: 240px;
    min-height: 0;
  }

  .session-list {
    max-height: 130px;
  }
}
</style>
