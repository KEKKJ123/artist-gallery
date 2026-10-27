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

/** 收件箱一页。返回 { total, offset, limit, items } */
export function fetchInbox(offset = 0, limit = 200) {
  return getJson(`/api/inbox?offset=${offset}&limit=${limit}`)
}

/** 某文件夹（含子文件夹）一页；path 为空 = 全部已归档。返回 { folder, total, offset, limit, items } */
export function fetchFolder(path = '', offset = 0, limit = 200) {
  // 文件夹名可能含中文、空格、% 等，必须用 URLSearchParams 编码
  const q = new URLSearchParams({ path, offset: String(offset), limit: String(limit) })
  return getJson(`/api/folder?${q}`)
}

/** 左侧导航：{ inbox, archived, folders: [{path, name, depth, count, has_children}] } */
export function fetchFolders() {
  return getJson('/api/folders')
}

export function fetchPlatforms() {
  return getJson('/api/platforms')
}
