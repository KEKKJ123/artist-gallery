// 和后端说话的唯一出口。组件里不直接写 fetch。

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

async function getJson(url) {
  let resp
  try {
    resp = await fetch(url)
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
