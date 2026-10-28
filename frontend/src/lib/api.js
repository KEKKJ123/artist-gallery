// 和后端说话的唯一出口。组件里不直接写 fetch。

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

async function getJson(url, options) {
  let resp
  try {
    resp = await fetch(url, options)
  } catch {
    // 服务停了、网络断了
    throw new ApiError('连不上服务，请确认 artist-gallery serve 还在运行', 0)
  }
  if (!resp.ok) {
    let msg = `请求失败（${resp.status}）`
    try {
      const body = await resp.json()
      if (body?.error) msg = body.error
    } catch {
      /* 不是 JSON，用默认文案 */
    }
    throw new ApiError(msg, resp.status)
  }
  return resp.json()
}

/** 收件箱一页。filter：all / hint（只看有来源建议的）/ nohint。返回 { filter, total, offset, limit, items } */
export function fetchInbox(offset = 0, limit = 200, filter = 'all') {
  const q = new URLSearchParams({ offset: String(offset), limit: String(limit), filter })
  return getJson(`/api/inbox?${q}`)
}

/** 已归档一页，按图片状态而不是目录查询。 */
export function fetchArchived(offset = 0, limit = 200) {
  return getJson(`/api/archived?${new URLSearchParams({ offset, limit })}`)
}
export function fetchNavigation() {
  return getJson('/api/navigation')
}

export function fetchPlatforms() {
  return getJson('/api/platforms')
}

// 写操作不自动重试：网络失败不代表服务端没有执行，先刷新状态再决定。
function writeJson(url, payload, method = 'POST', libraryId) {
  return getJson(url, {
    method,
    headers: { 'Content-Type': 'application/json', 'X-Artist-Gallery': '1', ...(libraryId ? { 'X-Gallery-Library': libraryId } : {}) },
    body: JSON.stringify(payload),
  })
}
export const fetchMetadata = () => getJson('/api/library')
export const fetchImage = (id) => getJson(`/api/images/${id}`)
export const fetchFileSize = (id) => getJson(`/api/images/${id}/size`)
export const fetchDraft = (id) => getJson(`/api/images/${id}/draft`)
export const putDraft = (id, payload, revision, libraryId) => writeJson(`/api/images/${id}/draft`, { payload, revision }, 'PUT', libraryId)
export const parseLinks = (text) => writeJson('/api/review/parse', { text })
export const saveReview = (payload, libraryId) => writeJson('/api/review/save', payload, 'POST', libraryId)
export const planArchive = (ids, force = false, libraryId) => writeJson('/api/archive/plan', { ids, force }, 'POST', libraryId)
export const executeArchive = (payload, libraryId) => writeJson('/api/archive', payload, 'POST', libraryId)
export const undoOperation = (id, libraryId) => writeJson('/api/undo', { id }, 'POST', libraryId)
export const recoverOperation = (id, action, libraryId) => writeJson('/api/recover', { id, action, confirmed: true }, 'POST', libraryId)
