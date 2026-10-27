<script setup>
// 收件箱的来源建议筛选：全部 / 有建议 / 没建议。只在收件箱视图里出现。
// 三个按钮各带张数，让人一眼知道"还有多少没处理"。
import { computed } from 'vue'
import { useInboxStore } from '../stores/inbox.js'
import { useLibraryStore } from '../stores/library.js'

const emit = defineEmits(['change'])
const inbox = useInboxStore()
const library = useLibraryStore()

const options = computed(() => {
  const all = library.nav.inbox
  const hinted = library.nav.inbox_hinted
  return [
    { id: 'all', label: '全部', count: all },
    { id: 'hint', label: '有来源建议', count: hinted },
    { id: 'nohint', label: '没有建议', count: Math.max(0, all - hinted) },
  ]
})
</script>

<template>
  <div class="bar" role="radiogroup" aria-label="按来源建议筛选">
    <button
      v-for="o in options"
      :key="o.id"
      class="chip"
      role="radio"
      :aria-checked="inbox.hintFilter === o.id"
      :class="{ on: inbox.hintFilter === o.id }"
      @click="emit('change', o.id)"
    >
      {{ o.label }}<span class="n">{{ o.count }}</span>
    </button>
  </div>
</template>

<style scoped>
.bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px var(--pad);
  background: var(--bg-elev);
  border-bottom: 1px solid var(--border);
  overflow-x: auto;
  scrollbar-width: none;
}
.bar::-webkit-scrollbar {
  display: none;
}
.chip {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 12px;
  border-radius: 999px;
  white-space: nowrap;
}
.chip.on {
  background: var(--accent-soft);
  border-color: var(--accent);
  font-weight: 600;
}
.n {
  font-size: 12px;
  color: var(--fg-dim);
  font-variant-numeric: tabular-nums;
}
.chip.on .n {
  color: var(--fg);
}
</style>
