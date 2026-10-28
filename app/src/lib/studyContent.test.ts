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
    expect(text).toContain('The 3D preview is a labelled synthetic shape, not data.') // the one thing drawn that is not from Python
  })
})
