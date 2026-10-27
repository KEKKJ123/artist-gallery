// 站点的显示信息（名称、标志颜色、标志上的字）。纯数据 + 纯函数，方便测试。
//
// 标志是"自己画的简化标志"：品牌主色的圆角方块 + 白色首字母，由组件用 SVG/CSS 绘制，
// 不内嵌各站点的官方 Logo 文件（那是注册商标，放进 GPL 开源仓库有版权/商标风险）。
//
// 自定义平台（用户在数据库里加的，platform 表 builtin=0）没有预设：用平台 id 稳定地算出一个颜色，
// 首字母取名称第一个字符。同一个平台每次颜色都一样，不同平台大概率不同。

const BUILTIN = {
  pixiv: { name: 'Pixiv', color: '#0096fa', letter: 'P' },
  x: { name: 'X', color: '#111111', letter: 'X' },
  zerochan: { name: 'Zerochan', color: '#6a4c93', letter: 'Z' },
}

/** 简单的字符串哈希（djb2），只用来给自定义平台挑颜色，不涉及安全。 */
function hash(str) {
  let h = 5381
  for (let i = 0; i < str.length; i++) h = ((h << 5) + h + str.charCodeAt(i)) >>> 0
  return h
}

/** 自定义平台的颜色：固定饱和度和亮度，只变色相，保证白字永远看得清。 */
function colorFor(id) {
  return `hsl(${hash(String(id)) % 360}, 55%, 38%)`
}

/** 取第一个"字"（按码点，不会把 emoji 或生僻汉字劈成乱码），大写。 */
function firstChar(text) {
  const c = [...String(text ?? '').trim()][0]
  return c ? c.toUpperCase() : '?'
}

/**
 * 站点显示信息。platformId 为空返回 null（表示"没有来源信息"，不画标志）。
 * names 可选：{ platformId: '显示名' }，来自 /api/platforms，用于自定义平台。
 */
export function platformInfo(platformId, names = {}) {
  if (!platformId) return null
  const id = String(platformId)
  if (BUILTIN[id]) return { id, ...BUILTIN[id] }
  // 显示名为空或全是空白时，用平台 id 兜底（否则标志上会是个没意义的 "?"）
  const given = String(names[id] ?? '').trim()
  const name = given || id
  return { id, name, color: colorFor(id), letter: firstChar(name) }
}

/**
 * 缩略图左下角标志的完整描述：
 *   { platform: {id,name,color,letter}, certain: bool, tooltip }
 * certain=false 表示"只知道大概来自哪个站点，还缺具体作品"（X 网页另存的 media key），标志上会加个 ? 点。
 * 没有来源建议返回 null。
 */
export function hintBadge(hint, names = {}) {
  if (!hint || !hint.platform) return null
  const platform = platformInfo(hint.platform, names)
  const certain = Boolean(hint.post_id)
  const tooltip = certain
    ? `可能是 ${platform.name}:${hint.post_id}`
    : `可能来自 ${platform.name}，需补链接`
  return { platform, certain, tooltip }
}
