// @vitest-environment node
// 静态依赖守护：新增功能不能把刚拆开的模块又接成环。
import { readdirSync, readFileSync } from 'node:fs'
import { dirname, extname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, it } from 'vitest'

const root = fileURLToPath(new URL('../src', import.meta.url))
function sources(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name)
    return entry.isDirectory() ? sources(path) : /\.(js|vue)$/.test(path) ? [path] : []
  })
}
const files = sources(root)
function imports(file) {
  return [...readFileSync(file, 'utf8').matchAll(/\bfrom\s+['"]([^'"]+)['"]/g)].map((m) => m[1])
}

it('纯逻辑不依赖组件、store、Vue 或网络；composables 不反向依赖 store/组件', () => {
  for (const file of files) {
    const rel = file.slice(root.length + 1).replaceAll('\\', '/')
    const deps = imports(file)
    if (rel.startsWith('lib/')) {
      expect(deps.filter((p) => /(?:components|stores|composables)\//.test(p) || p === 'vue' || p === 'pinia'), rel).toEqual([])
    }
    if (rel.startsWith('composables/')) {
      expect(deps.filter((p) => /(?:components|stores)\//.test(p) || p === 'pinia' || p.endsWith('/api.js')), rel).toEqual([])
    }
    if (rel.startsWith('stores/')) {
      expect(deps.filter((p) => /components\//.test(p)), rel).toEqual([])
    }
  }
})

it('本地模块 import 不成环，且文件名大小写逐字匹配（Windows 也检查）', () => {
  const edges = new Map(files.map((f) => [f, imports(f).filter((p) => p.startsWith('.')).map((p) => {
    const target = resolve(dirname(f), p)
    expect(extname(target), p).not.toBe('')
    expect(readdirSync(dirname(target)), p).toContain(target.slice(dirname(target).length + 1))
    return target
  })]))
  const done = new Set()
  function visit(file, stack) {
    expect(stack.includes(file), stack.concat(file).join(' → ')).toBe(false)
    if (done.has(file)) return
    for (const next of edges.get(file) ?? []) visit(next, stack.concat(file))
    done.add(file)
  }
  for (const file of files) visit(file, [])
})
