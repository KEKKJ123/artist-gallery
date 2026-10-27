<script setup>
import { computed } from 'vue'
import { hintLabel } from '../lib/format.js'
import { hintBadge } from '../lib/platforms.js'
import { useInboxStore } from '../stores/inbox.js'
import PlatformBadge from './PlatformBadge.vue'

const inbox = useInboxStore()
const n = computed(() => inbox.selected.size)
const one = computed(() => (n.value === 1 ? inbox.selectedItems[0] : null))
const badge = computed(() => (one.value ? hintBadge(one.value.source_hint, inbox.platformNames) : null))

// 选中的图里有多少带来源建议
const withHint = computed(() => inbox.selectedItems.filter((i) => i.source_hint).length)
</script>

<template>
  <aside class="panel" aria-label="操作面板">
    <header>
      <template v-if="n === 0">未选中图片</template>
      <template v-else>
        已选 <strong>{{ n }}</strong> 张
        <button class="link" @click="inbox.clearSelection()">取消选择</button>
      </template>
    </header>

    <section v-if="n === 0" class="empty">
      <p>点击图片选中，<kbd>Ctrl</kbd> 点击增减，<kbd>Shift</kbd> 点击选一段。</p>
      <p>按 <kbd>?</kbd> 查看全部快捷键。</p>
    </section>

    <section v-else-if="one" class="detail">
      <dl>
        <dt>原文件名</dt>
        <dd>{{ one.orig_name || '—' }}</dd>
        <dt>图库路径</dt>
        <dd class="mono">{{ one.rel_path }}</dd>
        <dt v-if="one.width">尺寸</dt>
        <dd v-if="one.width">{{ one.width }} × {{ one.height }}</dd>
        <dt>来源建议</dt>
        <dd class="hintrow">
          <template v-if="badge">
            <PlatformBadge :platform="badge.platform" :uncertain="!badge.certain" :size="20" />
            <span>{{ hintLabel(one.source_hint) }}</span>
          </template>
          <template v-else>无</template>
        </dd>
      </dl>
    </section>

    <section v-else class="detail">
      <p>共 {{ n }} 张，其中 {{ withHint }} 张带来源建议。</p>
    </section>

    <section v-if="inbox.isInbox" class="todo">
      <h3>归档与打 tag</h3>
      <p>粘贴链接归档、绑定画师、打 tag 将在后续版本加入（M1c / M1d）。</p>
    </section>
    <section v-else class="todo">
      <h3>只读浏览</h3>
      <p>文件夹视图目前只能查看，不能在这里移动或修改图片。</p>
    </section>
  </aside>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  gap: var(--pad);
  height: 100%;
  padding: var(--pad);
  overflow-y: auto;
  background: var(--bg-elev);
  border-left: 1px solid var(--border);
}
header {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 28px;
  font-size: 14px;
}
header strong {
  font-size: 16px;
  color: var(--accent);
}
.link {
  margin-left: auto;
  padding: 0 4px;
  border: none;
  background: none;
  color: var(--fg-dim);
  text-decoration: underline;
}
.empty,
.todo p {
  color: var(--fg-dim);
  font-size: 13px;
}
.empty p,
.todo p,
.detail p {
  margin: 0 0 6px;
}
dl {
  margin: 0;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px 12px;
  font-size: 13px;
}
dt {
  color: var(--fg-dim);
}
dd {
  margin: 0;
  min-width: 0;
  overflow-wrap: anywhere;
}
.hintrow {
  display: flex;
  align-items: center;
  gap: 6px;
}
.mono {
  font-family: ui-monospace, 'Cascadia Mono', Consolas, monospace;
  font-size: 12px;
}
.todo {
  margin-top: auto;
  padding-top: var(--pad);
  border-top: 1px dashed var(--border);
}
.todo h3 {
  margin: 0 0 4px;
  font-size: 13px;
}
</style>
