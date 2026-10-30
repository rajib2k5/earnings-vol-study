// Milestone 5 additions (the milestone list 0 to 5 with its pages, the About text on the 3D view). Mutations these
// tests and their companions in StudySections.test.tsx and App.test.tsx were seen to fail on (each applied, the
// tests run, the file restored and its SHA-256 compared):
//   A1 StudySections drops the "pages:" line; A2 a page label misspelt ('Implied vs Realised'); A3 milestone 5 marked
//   'done'; A4 milestone 5 removed; A5 the About text says the 3D view is synthetic again; A6 '3D view' listed under
//   two milestones (M0 and M3); A7 'Heatmap' listed under none.
import { describe, it, expect } from 'vitest'
import { ABOUT_INTRO, DISCLAIMER, MILESTONES, PITCH, QUESTIONS } from './studyContent'

const dupes = (xs: string[]) => xs.filter((x, i) => xs.indexOf(x) !== i)

describe('questions, milestones and disclaimer', () => {
  it('lists the study questions, each non-empty and unique', () => {
    expect(QUESTIONS.length).toBeGreaterThanOrEqual(5)
    expect(dupes(QUESTIONS)).toEqual([])
    for (const q of QUESTIONS) expect(q.trim().length).toBeGreaterThan(0)
  })
  it('has unique non-negative integer milestone ids with a known status', () => {
    expect(MILESTONES.length).toBeGreaterThanOrEqual(1)
    expect(dupes(MILESTONES.map((m) => String(m.id)))).toEqual([])
    for (const m of MILESTONES) {
      expect(Number.isInteger(m.id) && m.id >= 0).toBe(true)
      expect(['planned', 'in progress', 'done']).toContain(m.status)
    }
  })
  it('lists milestones 0 to 5 in order, 0 to 4 done and the report (5) still in progress', () => {
    expect(MILESTONES.map((m) => m.id)).toEqual([0, 1, 2, 3, 4, 5])
    expect(MILESTONES.map((m) => m.status)).toEqual(['done', 'done', 'done', 'done', 'done', 'in progress'])
  })
  it('names each app page under exactly one milestone, and only milestone 5 adds none', () => {
    const pages = MILESTONES.flatMap((m) => m.pages)
    expect(dupes(pages)).toEqual([])
    for (const p of pages) expect(p.trim().length).toBeGreaterThan(0)
    expect(MILESTONES.filter((m) => m.pages.length === 0).map((m) => m.id)).toEqual([5])
  })
  it('says "Not financial advice" and carries a one-sentence-plus pitch', () => {
    expect(DISCLAIMER).toMatch(/^Not financial advice\./)
    expect(PITCH.length).toBeGreaterThan(40)
  })
})

describe('about intro', () => {
  it('starts with the pitch and says no result is calculated in the browser (not that nothing is)', () => {
    expect(ABOUT_INTRO[0]).toBe(PITCH)
    const text = ABOUT_INTRO.join(' ')
    expect(text).toContain('no result is calculated in the browser')
    expect(text).not.toContain('nothing on screen is calculated')
    expect(text).not.toContain('synthetic') // the 3D view has drawn terrain.json since milestone 3
    expect(text).toContain('The 3D view draws the exported terrain file')
  })
})
