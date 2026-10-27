import { describe, expect, it } from 'vitest'
import { INBOX_VIEW, cleanFilter, parseView, sameView, viewToUrl } from '../src/lib/location.js'

describe('两区视图与地址栏', () => {
  it('默认收件箱，筛选服务端处理且可收藏', () => {
    expect(parseView('')).toEqual(INBOX_VIEW)
    expect(parseView('?filter=hint')).toEqual({kind:'inbox',filter:'hint'})
    expect(parseView('?filter=nohint')).toEqual({kind:'inbox',filter:'nohint'})
    expect(parseView('?filter=invalid')).toEqual(INBOX_VIEW)
    expect(cleanFilter('HINT')).toBe('all')
  })
  it('已归档不是平台文件夹，优先于收件箱筛选', () => {
    expect(parseView('?view=archived&filter=hint')).toEqual({kind:'archived'})
    expect(viewToUrl({kind:'archived'})).toBe('/?view=archived')
  })
  it('旧平台书签明确标记失效，不暗中解释为来源筛选', () => {
    for (const folder of ['pixiv','', '..','我的收藏']) {
      expect(parseView(`?folder=${encodeURIComponent(folder)}`)).toEqual({...INBOX_VIEW,legacy:true})
    }
  })
  it('状态／筛选往返一致', () => {
    for (const v of [INBOX_VIEW,{kind:'archived'}, {kind:'inbox',filter:'hint'}, {kind:'inbox',filter:'nohint'}]) {
      expect(parseView(viewToUrl(v).slice(1))).toEqual(v)
    }
  })
  it('同一状态和相同筛选才相等', () => {
    expect(sameView(INBOX_VIEW,{kind:'inbox'})).toBe(true)
    expect(sameView(INBOX_VIEW,{kind:'archived'})).toBe(false)
    expect(sameView(INBOX_VIEW,{kind:'inbox',filter:'hint'})).toBe(false)
    expect(sameView({kind:'archived'},{kind:'archived'})).toBe(true)
  })
})
