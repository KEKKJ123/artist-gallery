<script setup>
import { Images, Inbox } from '@lucide/vue'
import { useInboxStore } from '../stores/inbox.js'
import { useLibraryStore } from '../stores/library.js'

const emit = defineEmits(['navigate'])
const inbox = useInboxStore()
const library = useLibraryStore()
</script>

<template>
  <nav class="nav" aria-label="图库导航">
    <button
      class="row"
      :class="{ active: inbox.isInbox }"
      @click="emit('navigate', { kind: 'inbox', filter: 'all' })"
    >
      <Inbox :size="16" />
      <span class="label">收件箱</span>
      <span class="count">{{ library.nav.inbox }}</span>
    </button>
    <button
      class="row"
      :class="{ active: !inbox.isInbox }"
      @click="emit('navigate', { kind: 'archived' })"
    >
      <Images :size="16" />
      <span class="label">已归档</span>
      <span class="count">{{ library.nav.archived }}</span>
    </button>
    <p class="hint">新导入的图片先进入收件箱。平台是来源信息，不再拆分文件夹。</p>
  </nav>
</template>

<style scoped>
.nav {
  display: flex;
  flex-direction: column;
  gap: 1px;
  height: 100%;
  padding: 8px;
  overflow-y: auto;
  background: var(--bg-elev);
  border-right: 1px solid var(--border);
}
.row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: none;
  width: 100%;
  min-width: 0;
  padding: 5px 8px;
  text-align: left;
  border: none;
  background: transparent;
  border-radius: var(--radius);
}
.row:hover {
  background: var(--bg-sunken);
}
.row.active {
  background: var(--accent-soft);
  color: var(--fg);
  font-weight: 600;
}
.label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.count {
  font-size: 12px;
  color: var(--fg-dim);
  font-variant-numeric: tabular-nums;
}
.hint {
  margin: 12px 8px;
  font-size: 12px;
  color: var(--fg-dim);
}
@media (pointer: coarse) {
  .row {
    min-height: var(--touch);
  }
}
</style>
