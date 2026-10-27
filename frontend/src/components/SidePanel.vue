<script setup>
import { computed } from 'vue'
import { hintLabel } from '../lib/format.js'
import { useInboxStore } from '../stores/inbox.js'

const inbox = useInboxStore()
const n = computed(() => inbox.selected.size)
const one = computed(() => (n.value === 1 ? inbox.selectedItems[0] : null))

// 选中的图里有多少带来源建议
const withHint = computed(() => inbox.selectedItems.filter((i) => i.source_hints?.length).length)
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
      <p>按 <kbd>/</kbd> 查看全部快捷键，再按一次关闭（<kbd>Shift+/</kbd> 也可以）。</p>
    </section>

    <section v-else-if="one" class="detail">
      <dl>
        <dt>原文件名</dt>
        <dd>{{ one.orig_name || '—' }}</dd>
        <dt>图库路径</dt>
        <dd class="mono">{{ one.rel_path }}</dd>
        <dt v-if="one.width">尺寸</dt>
        <dd v-if="one.width">{{ one.width }} × {{ one.height }}</dd>
        <dt>画师</dt>
        <dd>{{ one.artist?.name || '未知' }}</dd>
        <dt>内容 tag</dt>
        <dd>{{ one.tags?.map(t => t.ns ? `${t.ns}:${t.name}` : t.name).join('、') || '无' }}</dd>
        <dt>来源建议</dt>
        <dd>
          <div v-for="(hint, i) in one.source_hints" :key="i" class="hintrow">
            {{ hintLabel(hint) }}<span v-if="hint.page != null"> · p{{ hint.page }}</span>
          </div>
          <span v-if="!one.source_hints?.length">无</span>
        </dd>
        <dt>已确认来源</dt>
        <dd>
          <div
            v-for="source in one.sources?.filter(s => s.status === 'confirmed')"
            :key="`${source.platform}:${source.post_id}`"
            class="hintrow"
          >
            {{ source.platform }}:{{ source.post_id }}<span v-if="source.page != null"> · p{{ source.page }}</span>
            <div v-if="source.posted_at">发布于 {{ source.posted_at }}</div>
          </div>
          <span v-if="!one.sources?.some(s => s.status === 'confirmed')">无</span>
        </dd>
      </dl>
    </section>

    <section v-else class="detail">
      <p>共 {{ n }} 张，其中 {{ withHint }} 张带来源建议。</p>
    </section>

    <section v-if="inbox.isInbox" class="todo">
      <h3>归档与打 tag</h3>
      <p>粘贴链接归档、绑定画师、打 tag 将在后续版本加入（T2 / T3）。</p>
    </section>
    <section v-else class="todo">
      <h3>只读浏览</h3>
      <p>已归档视图当前只读，来源核查与编辑将在后续加入。</p>
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
  display: block;
  margin-bottom: 4px;
  overflow-wrap: anywhere;
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
