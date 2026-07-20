import { describe, expect, it } from 'vitest'
import { recipeSuccessFixture } from '@/fixtures/recipe'
import { buildXiaohongshuShareDraft } from '../xiaohongshuShare'

describe('buildXiaohongshuShareDraft', () => {
  it('turns the saved recipe into an editable share draft using only recipe data', () => {
    const draft = buildXiaohongshuShareDraft(recipeSuccessFixture)

    expect(draft).toContain('番茄炒蛋')
    expect(draft).toContain('超简单番茄炒蛋，学会你也是大厨')
    expect(draft).toContain('今天安排番茄炒蛋，真的嘎嘎下饭')
    expect(draft).toContain('适合 2 人 | 约 20 分钟 | 简单')
    expect(draft).toContain('- 番茄2个')
    expect(draft).toContain('1. 番茄洗净切块。')
    expect(draft).toContain('#今日菜谱 #家常菜 #下饭菜 #新手学做菜 #番茄炒蛋')
    expect(draft).not.toContain('食材由 VisAgent 识别后经人工确认')
  })

  it('keeps an incomplete recipe readable without adding fabricated ingredients or steps', () => {
    const draft = buildXiaohongshuShareDraft({ title: '清爽晚餐', ingredients: [], steps: [] })

    expect(draft).toContain('清爽晚餐')
    expect(draft).not.toContain('食材准备：')
    expect(draft).not.toContain('做法：')
    expect(draft).not.toContain('undefined')
  })
})
