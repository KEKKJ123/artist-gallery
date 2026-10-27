import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, it } from 'vitest'
import SidePanel from '../src/components/SidePanel.vue'
import NavPanel from '../src/components/NavPanel.vue'
import { useInboxStore } from '../src/stores/inbox.js'
import { useLibraryStore } from '../src/stores/library.js'
import { imageCaption } from '../src/lib/format.js'

beforeEach(() => setActivePinia(createPinia()))
it('详情完整显示多来源、可空平台页码与直接角色 tag／画师', () => {
  const store = useInboxStore()
  store.items = [{id:1,orig_name:'原名.png',rel_path:'images/_inbox/原名.png',tags:[{ns:'character',name:'红豆'}],artist:{id:1,name:'画师甲'},source_hints:[{platform:'pixiv',post_id:'123456789',page:2},{platform:'x',post_id:'1849000000000000000',page:null}],sources:[]}]
  store.click(1)
  const w = mount(SidePanel)
  expect(w.text()).toContain('character:红豆')
  expect(w.text()).toContain('画师甲')
  expect(w.text()).toContain('123456789')
  expect(w.text()).toContain('1849000000000000000')
  expect(w.text()).toContain('p2')
  expect(w.text()).not.toContain('p0')
  w.unmount()
})
it('导航只有两区，点击不产生文件夹或分组', async () => {
  useLibraryStore().nav = {inbox:3,inbox_hinted:2,archived:1}
  const w = mount(NavPanel)
  const buttons=w.findAll('button')
  expect(buttons).toHaveLength(2)
  await buttons[1].trigger('click')
  expect(w.emitted('navigate')).toEqual([[{kind:'archived'}]])
  w.unmount()
})
it('标题不将未知 pn 填成 p0，确认来源优先，原名作为回退', () => {
  expect(imageCaption({orig_name:'a.png',source_hints:[{post_id:'123'}]})).toBe('疑似 123')
  expect(imageCaption({sources:[{status:'confirmed',post_id:'456',page:0}],source_hints:[{post_id:'123'}]})).toBe('456_p0')
  expect(imageCaption({orig_name:'原名.png',source_hints:[{platform:'x'}]})).toBe('原名.png')
  expect(imageCaption({})).toBe('未命名')
})
