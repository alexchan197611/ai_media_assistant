import type { Segment } from '../../types'
const createSegment = (text: string, order: number): Segment => ({ id: crypto.randomUUID(), order, text, marks: [], text_color: null, background_asset_id: null, background_motion: null, background_position_x: 0.5, background_position_y: 0.5, tts_audio_asset_id: null, audio_duration_ms: null, status: 'draft' })

type TextRange = { start: number; end: number }

function validateMarks(segment: Segment, text: string): Segment['marks'] {
  return normalizeMarks(text, segment.marks.flatMap(mark => {
    const selected = String(mark.text ?? '')
    if (!selected) return []
    const start = Number(mark.start)
    const end = Number(mark.end)
    if (Number.isInteger(start) && Number.isInteger(end) && text.slice(start, end) === selected) return [{ ...mark, start, end, text: selected, kind: mark.kind ?? 'highlight' }]
    const nextStart = text.indexOf(selected)
    if (nextStart < 0) return []
    return [{ ...mark, start: nextStart, end: nextStart + selected.length, text: selected, kind: mark.kind ?? 'highlight' }]
  }))
}

function segmentRanges(segments: Segment[]): TextRange[] {
  let cursor = 0
  return segments.map(segment => {
    const start = cursor
    const end = start + segment.text.length
    cursor = end + 1
    return { start, end }
  })
}

function normalizeMarks(text: string, marks: Segment['marks']): Segment['marks'] {
  const ranges = marks.flatMap(mark => {
    const start = Math.max(0, Math.min(text.length, Number(mark.start)))
    const end = Math.max(start, Math.min(text.length, Number(mark.end)))
    if (!Number.isInteger(start) || !Number.isInteger(end) || end <= start) return []
    return [{ start, end }]
  }).sort((a, b) => a.start - b.start)

  const merged: TextRange[] = []
  for (const range of ranges) {
    const previous = merged.at(-1)
    if (previous && range.start <= previous.end) {
      previous.end = Math.max(previous.end, range.end)
    } else {
      merged.push({ ...range })
    }
  }
  return merged.map(range => ({ start: range.start, end: range.end, text: text.slice(range.start, range.end), kind: 'highlight' }))
}

export function syncSegments(text: string, previous: Segment[], preserveEditedPosition = false): Segment[] {
  const lines = text.split(/\r?\n/).map(line => line.trim()).filter(Boolean)
  const available = new Map<string, Segment[]>()
  for (const segment of previous) available.set(segment.text, [...(available.get(segment.text) ?? []), segment])
  return lines.map((line, order) => {
    const exact = available.get(line)?.shift()
    if (exact) return { ...exact, order }
    if (preserveEditedPosition && lines.length === previous.length && previous[order]) {
      const segment = previous[order]
      return { ...segment, order, text: line, marks: validateMarks(segment, line) }
    }
    return createSegment(line, order)
  })
}

export function applyHighlightSelection(segments: Segment[], selectionStart: number, selectionEnd: number): Segment[] {
  const start = Math.min(selectionStart, selectionEnd)
  const end = Math.max(selectionStart, selectionEnd)
  if (start === end) return segments
  const ranges = segmentRanges(segments)
  return segments.map((segment, index) => {
    const range = ranges[index]
    const overlapStart = Math.max(start, range.start)
    const overlapEnd = Math.min(end, range.end)
    if (overlapEnd <= overlapStart) return segment
    const localStart = overlapStart - range.start
    const localEnd = overlapEnd - range.start
    const selected = segment.text.slice(localStart, localEnd)
    if (!selected.trim()) return segment
    return {
      ...segment,
      marks: normalizeMarks(segment.text, [...segment.marks, { start: localStart, end: localEnd, text: selected, kind: 'highlight' }]),
    }
  })
}

export function removeHighlightSelection(segments: Segment[], selectionStart: number, selectionEnd: number): Segment[] {
  const start = Math.min(selectionStart, selectionEnd)
  const end = Math.max(selectionStart, selectionEnd)
  if (start === end) return segments
  const ranges = segmentRanges(segments)
  return segments.map((segment, index) => {
    const range = ranges[index]
    const overlapStart = Math.max(start, range.start)
    const overlapEnd = Math.min(end, range.end)
    if (overlapEnd <= overlapStart) return segment
    const localStart = overlapStart - range.start
    const localEnd = overlapEnd - range.start
    const nextMarks = segment.marks.flatMap(mark => {
      const markStart = Number(mark.start)
      const markEnd = Number(mark.end)
      if (markEnd <= localStart || markStart >= localEnd) return [mark]
      const split: Segment['marks'] = []
      if (markStart < localStart) split.push({ start: markStart, end: localStart, text: segment.text.slice(markStart, localStart), kind: 'highlight' })
      if (markEnd > localEnd) split.push({ start: localEnd, end: markEnd, text: segment.text.slice(localEnd, markEnd), kind: 'highlight' })
      return split
    })
    return { ...segment, marks: normalizeMarks(segment.text, nextMarks) }
  })
}

export function clearHighlights(segments: Segment[]): Segment[] {
  return segments.map(segment => segment.marks.length ? { ...segment, marks: [] } : segment)
}
