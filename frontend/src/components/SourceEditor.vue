<script setup>
import { useLibraryStore } from '../stores/library.js'
import { useReviewStore } from '../stores/review.js'
const review = useReviewStore()
const library = useLibraryStore()
const statuses = { pending: '待核查', confirmed: '已人工确认', rejected: '已驳回' }
function value(source, field) {
  const edit = review.draft?.edits[source.id]
  return edit && Object.hasOwn(edit, field) ? edit[field] : source[field]
}
function url(source) {
  const template = library.platforms.find((p) => p.id === source.platform)?.post_url
  if (!template || !/^https?:\/\//.test(template)) return null
  return template.replace('{post_id}', encodeURIComponent(source.post_id))
}
function pageInput(source, raw) {
  if (!raw) review.editSource(source, 'page', null)
  else review.editSource(source, 'page', /^\d+$/.test(raw) && Number.isSafeInteger(Number(raw)) ? Number(raw) : raw)
}
</script>

<template>
  <h2>已有来源</h2>
  <p v-if="!review.item.sources.length" class="muted">还没有具体发布来源，可在下方粘贴链接。</p>
  <article v-for="source in review.item.sources" :key="source.id" class="source-card">
    <div class="source-heading">
      <strong>{{ source.platform }}:{{ source.post_id }}</strong>
      <a v-if="url(source)" :href="url(source)" target="_blank" rel="noopener noreferrer">打开发布 ↗</a>
    </div>
    <p class="saved-status">已保存：{{ statuses[source.status] }} · {{ source.page == null ? '页码未知' : `p${source.page}` }}</p>
    <template v-if="!review.draft.edits[source.id]?.remove">
      <label>核查决定
        <select :value="value(source, 'status')" :aria-label="`核查 ${source.platform}:${source.post_id}`"
          @change="review.editSource(source, 'status', $event.target.value)">
          <option value="pending">待核查</option>
          <option value="confirmed">已人工确认</option>
          <option value="rejected">已驳回</option>
        </select>
      </label>
      <div class="source-fields">
        <label>平台页码 pn（从 0 起，可空）
          <input :value="value(source, 'page') ?? ''" inputmode="numeric" placeholder="未知"
            :aria-label="`${source.platform} 页码`" @input="pageInput(source, $event.target.value)" />
        </label>
        <label>发布时间（带时区，可空）
          <input :value="value(source, 'posted_at') ?? ''" placeholder="2026-10-28T12:00:00+08:00"
            :aria-label="`${source.platform} 发布时间`" @input="review.editSource(source, 'posted_at', $event.target.value)" />
        </label>
      </div>
      <label v-if="source.time_image_ids?.length > 1 && value(source, 'posted_at') !== source.posted_at" class="time-scope">
        <input type="checkbox" :checked="!!review.draft.edits[source.id]?.time_scope_ids"
          @change="review.editSource(source, 'time_scope_ids', $event.target.checked ? source.time_image_ids : null)" />
        我确认修改此发布的共享时间，影响图片 #{{ source.time_image_ids.join('、#') }}；不修改这些图片的其他资料。
      </label>
      <button class="remove" @click="review.editSource(source, 'remove', true)">解除这条来源</button>
    </template>
    <div v-else class="remove-notice">
      保存后只解除这张图片与发布的关联，证据仍保留。
      <button @click="review.editSource(source, 'remove', false)">取消解除</button>
    </div>
    <details>
      <summary>查看识别／输入依据</summary>
      <ul>
        <li v-for="evidence in review.item.evidence.filter((e) => e.source_id === source.id)" :key="evidence.id">
          {{ evidence.input_kind === 'filename' ? '文件名' : '链接' }}：{{ evidence.input_text }}
          <span v-if="evidence.page != null"> · 线索 p{{ evidence.page }}</span>
        </li>
      </ul>
    </details>
  </article>
  <details v-if="review.item.evidence.some((e) => e.source_id == null)" class="loose-evidence">
    <summary>其他／已解除线索（保留依据）</summary>
    <article v-for="e in review.item.evidence.filter((e) => e.source_id == null)" :key="e.id">
      <p>{{ e.platform }} · {{ e.input_text }}</p>
      <label><input type="checkbox" :checked="review.draft.evidence_edits[e.id]?.dismissed ?? !!e.dismissed"
        @change="review.dismissEvidence(e, $event.target.checked)" /> 不再显示为待核查线索</label>
    </article>
  </details>
</template>

<style scoped>
h2 { margin: 0 0 8px; font-size: 15px; }
.source-card { padding: 10px; margin-bottom: 10px; border: 1px solid var(--border); border-radius: var(--radius); }
.source-heading { display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; overflow-wrap: anywhere; }
a { color: var(--accent); font-size: 12px; }
.saved-status, .muted { color: var(--fg-dim); font-size: 12px; }
label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; }
input, select { min-height: 36px; width: 100%; min-width: 0; padding: 6px; font: inherit; background: var(--bg); color: var(--fg); border: 1px solid var(--border); border-radius: var(--radius); }
.source-fields { display: grid; gap: 8px; margin-top: 8px; }
.remove { margin-top: 8px; color: var(--danger); }
details { font-size: 12px; margin-top: 10px; overflow-wrap: anywhere; }
summary { cursor: pointer; }
ul { padding-left: 16px; }
.remove-notice { padding: 8px 0; color: var(--warn); }
.loose-evidence label { flex-direction: row; align-items: center; }
.loose-evidence input { width: auto; }
</style>
