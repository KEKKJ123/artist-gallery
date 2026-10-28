// 每次输入立即写浏览器本地兜底，服务端草稿随后同步；不同图库和图片绝不混用。
const prefix = 'artist-gallery:review-draft:'
export function draftKey(libraryId, imageId) {
  return `${prefix}${libraryId}:${imageId}`
}
export function readLocalDraft(storage, libraryId, imageId) {
  try {
    const raw = storage.getItem(draftKey(libraryId, imageId))
    if (!raw) return null
    const record = JSON.parse(raw)
    if (!validDraft(record?.payload) || !Number.isSafeInteger(record.revision) || record.revision < 0) return null
    return record
  } catch { return null }
}
export function writeLocalDraft(storage, libraryId, imageId, record) {
  try {
    storage.setItem(draftKey(libraryId, imageId), JSON.stringify(record))
    return true
  } catch { return false }
}
export function removeLocalDraft(storage, libraryId, imageId, owner) {
  try {
    const current = readLocalDraft(storage, libraryId, imageId)
    if (!owner || current?.owner === owner) storage.removeItem(draftKey(libraryId, imageId))
  } catch { /* 保持服务端草稿 */ }
}
export function sameDraft(a, b) {
  const stable = (value) => {
    if (Array.isArray(value)) return value.map(stable)
    if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map((key) => [key, stable(value[key])]))
    return value
  }
  return JSON.stringify(stable(a)) === JSON.stringify(stable(b))
}
export function validDraft(payload) {
  return !!payload && typeof payload === 'object' && typeof payload.base === 'string'
    && typeof payload.text === 'string' && payload.text.length <= 64000
    && !!payload.edits && typeof payload.edits === 'object' && !Array.isArray(payload.edits)
    && !!payload.evidence_edits && typeof payload.evidence_edits === 'object' && !Array.isArray(payload.evidence_edits)
}
export function emptyDraft(item) {
  return { base: item.revision, text: '', edits: {}, evidence_edits: {} }
}
export function reviewPayload(draft, id) {
  return {
    ids: [id], revisions: { [id]: draft.base }, text: draft.text,
    edits: Object.values(draft.edits), evidence_edits: Object.values(draft.evidence_edits),
  }
}
export function formatBytes(bytes) {
  if (!Number.isSafeInteger(bytes) || bytes < 0) return '未知'
  const units = ['B', 'KiB', 'MiB', 'GiB']
  const n = Math.min(Math.floor(Math.log(Math.max(1, bytes)) / Math.log(1024)), 3)
  return n ? `${(bytes / 1024 ** n).toFixed(2)} ${units[n]}（${bytes.toLocaleString()} 字节）` : `${bytes} 字节`
}
