import { describe, it, expect } from 'vitest'
import { HEAT_LEGEND_GRADIENT, heatColour, legendLabels, maxAbs } from './heatColour'

// The scale runs blue rgb(33,102,172) at -max, near white rgb(247,247,247) at 0, red rgb(178,24,43) at +max.
// A channel at strength t is round(247 + (end - 247) * t), t = min(1, |value| / max).

describe('maxAbs', () => {
  it('is the largest absolute value of the non-null cells', () => {
    expect(maxAbs([[-3, 1], [null, 2]])).toBe(3)
    expect(maxAbs([[0.5, null], [-0.25, 0]])).toBe(0.5)
  })
  it('does not read null as anything: a grid of nulls (or no grid) has max 0', () => {
    expect(maxAbs([[null, null]])).toBe(0)
    expect(maxAbs([])).toBe(0)
    expect(maxAbs([[]])).toBe(0)
  })
  it('ignores a non-finite cell', () => {
    expect(maxAbs([[NaN, Infinity, -2]])).toBe(2)
  })
  it('counts a negative largest value by its size: -5 beats 4', () => {
    expect(maxAbs([[4, -5]])).toBe(5)
  })
})

describe('heatColour: diverging scale, symmetric around 0', () => {
  it('gives 0 the neutral colour', () => {
    expect(heatColour(0, 2)).toBe('rgb(247,247,247)')
  })
  it('gives +max the full red and -max the full blue', () => {
    expect(heatColour(2, 2)).toBe('rgb(178,24,43)')
    expect(heatColour(-2, 2)).toBe('rgb(33,102,172)')
  })
  it('blends halfway for half the max, by hand: +1 of 2 -> r 247 - 69/2 = 212.5 -> 213, g 247 - 223/2 = 135.5 -> 136, b 247 - 204/2 = 145', () => {
    expect(heatColour(1, 2)).toBe('rgb(213,136,145)')
  })
  it('blends the negative side the same way: -1 of 2 -> r 247 - 214/2 = 140, g 247 - 145/2 = 174.5 -> 175, b 247 - 75/2 = 209.5 -> 210', () => {
    expect(heatColour(-1, 2)).toBe('rgb(140,175,210)')
  })
  it('blends a quarter: 0.5 of 2 -> r 247 - 69/4 = 229.75 -> 230, g 247 - 223/4 = 191.25 -> 191, b 247 - 204/4 = 196', () => {
    expect(heatColour(0.5, 2)).toBe('rgb(230,191,196)')
  })
  it('is symmetric: +v and -v have the same strength (equal distance from neutral, in the direction of their own end colour)', () => {
    for (const t of [0.1, 0.3, 0.5, 0.9]) {
      const pos = heatColour(t, 1)?.match(/\d+/g)?.map(Number) ?? []
      const neg = heatColour(-t, 1)?.match(/\d+/g)?.map(Number) ?? []
      // fraction of the way from neutral to the end colour, per channel
      const posFrac = pos.map((c, i) => (247 - c) / (247 - [178, 24, 43][i]))
      const negFrac = neg.map((c, i) => (247 - c) / (247 - [33, 102, 172][i]))
      posFrac.forEach((f, i) => {
        expect(f).toBeCloseTo(t, 1)
        expect(negFrac[i]).toBeCloseTo(t, 1)
      })
    }
  })
  it('spans the grid\'s own max, not a fixed range: 0.2 of 0.2 is as strong as 1 of 1', () => {
    expect(heatColour(0.2, 0.2)).toBe(heatColour(1, 1))
    expect(heatColour(0.2, 0.2)).toBe('rgb(178,24,43)')
  })
  it('keeps 0 neutral when the grid has no negative values (not min-max: 0 is not the blue end)', () => {
    // a grid [0, 1]: max |value| is 1, so 0 stays neutral and 1 is full red
    expect(heatColour(0, maxAbs([[0, 1]]))).toBe('rgb(247,247,247)')
    expect(heatColour(1, maxAbs([[0, 1]]))).toBe('rgb(178,24,43)')
  })
  it('caps the strength at the max: a value beyond it gets the end colour', () => {
    expect(heatColour(5, 2)).toBe('rgb(178,24,43)')
    expect(heatColour(-5, 2)).toBe('rgb(33,102,172)')
  })
  it('gives a cell with no value NO colour (null), which is not the colour of 0', () => {
    expect(heatColour(null, 2)).toBeNull()
    expect(heatColour(0, 2)).not.toBeNull()
    expect(heatColour(NaN, 2)).toBeNull()
    expect(heatColour(Infinity, 2)).toBeNull()
  })
  it('leaves every cell neutral when the max is 0 (a grid of zeros), instead of dividing by zero', () => {
    expect(heatColour(0, 0)).toBe('rgb(247,247,247)')
    expect(heatColour(0.5, 0)).toBe('rgb(247,247,247)')
  })
})

describe('legend', () => {
  it('labels the ends -max and +max as the file has them', () => {
    expect(legendLabels(0.4352)).toEqual(['-0.4352', '+0.4352'])
    expect(legendLabels(2)).toEqual(['-2', '+2'])
  })
  it('labels a scale with no span 0 and 0', () => {
    expect(legendLabels(0)).toEqual(['0', '0'])
  })
  it('draws the gradient from the -max colour through neutral to the +max colour', () => {
    expect(HEAT_LEGEND_GRADIENT).toBe(`linear-gradient(to right, ${heatColour(-1, 1)}, ${heatColour(0, 1)}, ${heatColour(1, 1)})`)
  })
})
