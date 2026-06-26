import { describe, expect, it } from 'vitest'
import { applyHighlightSelection, clearHighlights, removeHighlightSelection, syncSegments } from './segments'
describe('syncSegments', () => {
  it('preserves ids for existing lines and creates UUIDs for new lines', () => {
    const first = syncSegments('第一行', [])
    const next = syncSegments('第一行\n第二行', first)
    expect(next[0].id).toBe(first[0].id)
    expect(next[1].id).not.toBe(first[0].id)
    expect(next[1].id).toMatch(/^[0-9a-f-]{36}$/)
  })
  it('does not let replacement lines inherit ids after deletion', () => {
    const original = syncSegments('旧第一行\n保留行', [])
    const replaced = syncSegments('全新行\n保留行', original)
    expect(replaced[0].id).not.toBe(original[0].id)
    expect(replaced[1].id).toBe(original[1].id)
  })
  it('repairs or removes stale highlight marks on edited lines', () => {
    const [original] = syncSegments('今天适合创作', [])
    const marked = { ...original, marks: [{ start: 2, end: 4, text: '适合', kind: 'highlight' }] }
    const repaired = syncSegments('真的适合创作', [marked], true)
    expect(repaired[0].id).toBe(marked.id)
    expect(repaired[0].marks[0]).toMatchObject({ start: 2, end: 4, text: '适合' })
    const removed = syncSegments('真的可以创作', [marked], true)
    expect(removed[0].marks).toEqual([])
  })
  it('adds highlights from textarea selection while preserving segment ids', () => {
    const segments = syncSegments('春风入画\n古寺闻钟', [])
    const highlighted = applyHighlightSelection(segments, 2, 8)
    expect(highlighted[0].id).toBe(segments[0].id)
    expect(highlighted[1].id).toBe(segments[1].id)
    expect(highlighted[0].marks).toEqual([{ start: 2, end: 4, text: '入画', kind: 'highlight' }])
    expect(highlighted[1].marks).toEqual([{ start: 0, end: 3, text: '古寺闻', kind: 'highlight' }])
  })
  it('removes only the selected part of existing highlights', () => {
    const [segment] = applyHighlightSelection(syncSegments('今天适合创作', []), 0, 6)
    const [removed] = removeHighlightSelection([segment], 2, 4)
    expect(removed.marks).toEqual([
      { start: 0, end: 2, text: '今天', kind: 'highlight' },
      { start: 4, end: 6, text: '创作', kind: 'highlight' },
    ])
    expect(clearHighlights([removed])[0].marks).toEqual([])
  })
})
