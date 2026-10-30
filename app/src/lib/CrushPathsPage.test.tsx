import { describe, it, expect, vi, afterEach } from 'vitest'
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { CrushPathsDisplay, CrushPathsPage } from './CrushPathsPage'
import { parseEventPaths, type EventPaths } from './eventPaths'
import { FRAME_MS } from './pathFrames'
import { EVENT_PATHS_DATA_FIXTURE, EVENT_PATHS_FIXTURE } from '../test/eventPathsFixture'
import { edited } from '../test/editHelpers'

const respond = (res: Partial<Response>) => vi.fn(async () => res as Response) as unknown as typeof fetch
const serving = (body: unknown) => respond({ ok: true, status: 200, json: async () => body })

/** The checked data for `CrushPathsDisplay`, built by the same validator the page uses, from the fixture data or an edited copy. */
function checked(data: unknown = EVENT_PATHS_DATA_FIXTURE): EventPaths {
  const r = parseEventPaths(data)
  if (!r.ok) throw new Error(r.error)
  return r.data
}

function setReducedMotion(reduce: boolean | undefined) {
  if (reduce === undefined) Reflect.deleteProperty(window, 'matchMedia')
  else Object.defineProperty(window, 'matchMedia', { configurable: true, value: () => ({ matches: reduce }) })
}

afterEach(() => {
  setReducedMotion(undefined)
  vi.useRealTimers()
})

/** The `d` of every per-event path, by event id, in document order. */
const eventPaths = (container: HTMLElement): [string, string][] =>
  [...container.querySelectorAll('path[data-event]')].map((p) => [p.getAttribute('data-event') ?? '', p.getAttribute('d') ?? ''])

const mean = (name: string) => screen.getByTestId(name).getAttribute('d') ?? ''
/** The y coordinates of a path string like "M56 10 L198 20". */
const ys = (d: string): number[] => [...d.matchAll(/[ML]\s*(-?[\d.]+) (-?[\d.]+)/g)].map((m) => Number(m[2]))
const xsOf = (d: string): number[] => [...d.matchAll(/[ML]\s*(-?[\d.]+) (-?[\d.]+)/g)].map((m) => Number(m[1]))
const count = (d: string, ch: string): number => d.split(ch).length - 1
/** One animation frame. Each frame needs its own act(): the next timer is only set once React has re-rendered. */
const tick = (frames = 1) => {
  for (let i = 0; i < frames; i++) act(() => void vi.advanceTimersByTime(FRAME_MS))
}

// x pixels of the fixture's five days (-2 .. 2): 56, 198, 340, 482, 624 (see pathFrames.test.ts).
const XS = [56, 198, 340, 482, 624]

describe('CrushPathsPage: loading and errors', () => {
  it('shows a loading line first, then the page', async () => {
    render(<CrushPathsPage fetchImpl={serving(EVENT_PATHS_FIXTURE)} />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading event paths')
    expect(screen.getByRole('heading', { level: 2, name: 'Crush paths' })).toBeInTheDocument()
    await screen.findByRole('img', { name: /Mean abnormal log IV path/ })
    expect(screen.queryByRole('status')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })
  it('requests the relative data/event_paths.json by default, and the given url when there is one', async () => {
    const f = serving(EVENT_PATHS_FIXTURE)
    const { unmount } = render(<CrushPathsPage fetchImpl={f} />)
    await screen.findByRole('img', { name: /Mean abnormal log IV path/ })
    expect(f).toHaveBeenCalledWith('data/event_paths.json', { cache: 'no-cache' })
    unmount()
    const g = serving(EVENT_PATHS_FIXTURE)
    render(<CrushPathsPage url="x/event_paths.json" fetchImpl={g} />)
    await screen.findByRole('img', { name: /Mean abnormal log IV path/ })
    expect(g).toHaveBeenCalledWith('x/event_paths.json', { cache: 'no-cache' })
  })
  it('shows an error with the message, and no chart, when the file is missing (HTTP 404)', async () => {
    render(<CrushPathsPage fetchImpl={respond({ ok: false, status: 404 })} />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('data error')
    expect(alert).toHaveTextContent('The event paths could not be shown')
    expect(alert).toHaveTextContent('HTTP 404')
    expect(screen.queryByRole('img')).toBeNull()
    expect(screen.queryByRole('button')).toBeNull()
  })
  it('shows an error for the previous schema version, another kind, and a ragged path', async () => {
    const { unmount } = render(<CrushPathsPage fetchImpl={serving({ ...EVENT_PATHS_FIXTURE, schema_version: '0.3.0' })} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('unsupported schema_version "0.3.0": this app only understands "0.5.0"')
    unmount()
    const other = render(<CrushPathsPage fetchImpl={serving({ ...EVENT_PATHS_FIXTURE, kind: 'terrain' })} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('has kind "terrain", expected "event_paths"')
    other.unmount()
    const body = { ...EVENT_PATHS_FIXTURE, data: edited(EVENT_PATHS_DATA_FIXTURE, ['per_event', 0, 'values'], [1, 2, 3]) }
    render(<CrushPathsPage fetchImpl={serving(body)} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('data/event_paths.json: per_event[0].values must have 5 entries (one per rel_days entry), got 3')
    expect(screen.queryByRole('img')).toBeNull()
  })
  it('ignores a late answer for an old url after the url has changed', async () => {
    let releaseOld: (r: Response) => void = () => {}
    const oldFetch = vi.fn(() => new Promise<Response>((r) => (releaseOld = r))) as unknown as typeof fetch
    const { rerender } = render(<CrushPathsPage url="old/event_paths.json" fetchImpl={oldFetch} />)
    rerender(<CrushPathsPage url="new/event_paths.json" fetchImpl={serving(EVENT_PATHS_FIXTURE)} />)
    await screen.findByRole('img', { name: /Mean abnormal log IV path/ })
    releaseOld({ ok: false, status: 500 } as Response)
    await new Promise((r) => setTimeout(r, 0))
    expect(screen.getByRole('img', { name: /Mean abnormal log IV path/ })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('CrushPathsDisplay: caveats and the provisional notice', () => {
  it('states that the timing labels are provisional and lists every caveat once', () => {
    render(<CrushPathsDisplay paths={checked()} />)
    expect(screen.getByRole('complementary', { name: 'Provisional timing labels' })).toHaveTextContent('Timing labels are provisional: 3 timing look-ups are done')
    for (const c of EVENT_PATHS_DATA_FIXTURE.caveats) expect(screen.getAllByText(c)).toHaveLength(1)
  })
})

describe('CrushPathsDisplay: the mean path chart and its selectors', () => {
  it('starts on the first adjustment and subgroup of the file (market, all), and offers exactly what the file has', () => {
    render(<CrushPathsDisplay paths={checked()} />)
    expect(screen.getByLabelText('Adjustment')).toHaveValue('market')
    expect(screen.getByLabelText('Subgroup')).toHaveValue('all=all')
    expect(within(screen.getByLabelText('Adjustment')).getAllByRole('option').map((o) => o.textContent)).toEqual(['market', 'mean'])
    expect(within(screen.getByLabelText('Subgroup')).getAllByRole('option').map((o) => o.textContent)).toEqual(['all', 'BMO', 'AMC'])
    expect(screen.getByRole('img', { name: 'Mean abnormal log IV path with its pointwise 95% band, market-adjusted, subgroup all' })).toBeInTheDocument()
  })
  it('draws the mean line at the pixel x of each event day, and breaks it where the mean is null (day 0)', () => {
    render(<CrushPathsDisplay paths={checked()} />)
    // mean [0.5, 1, null, 2, 2.5]: two runs, days -2, -1 and days 1, 2
    const d = mean('mean-line')
    expect(count(d, 'M')).toBe(2)
    expect(xsOf(d)).toEqual([XS[0], XS[1], XS[3], XS[4]])
    // higher value = smaller y (higher on screen)
    const y = ys(d)
    expect(y[1]).toBeLessThan(y[0]) // 1 above 0.5
    expect(y[3]).toBeLessThan(y[2]) // 2.5 above 2
    expect(y[2]).toBeLessThan(y[1]) // 2 above 1
  })
  it('draws the band as one closed polygon per stretch of days that have both edges (a gap at day 0)', () => {
    render(<CrushPathsDisplay paths={checked()} />)
    const d = mean('mean-band')
    expect(count(d, 'Z')).toBe(2)
    expect(count(d, 'M')).toBe(2)
    // each polygon visits its two days twice: upper edge then lower edge
    expect(xsOf(d)).toEqual([XS[0], XS[1], XS[1], XS[0], XS[3], XS[4], XS[4], XS[3]])
  })
  it('keeps the band around the mean: the upper edge is higher on screen than the line, the lower edge lower', () => {
    render(<CrushPathsDisplay paths={checked()} />)
    const line = ys(mean('mean-line'))
    const band = ys(mean('mean-band')) // first polygon: hi(-2), hi(-1), lo(-1), lo(-2)
    expect(band[0]).toBeLessThan(line[0])
    expect(band[3]).toBeGreaterThan(line[0])
  })
  it('switches to the mean adjustment and the BMO subgroup: a flat line 3, 3, 3, 3, 3 with one run over all five days', () => {
    render(<CrushPathsDisplay paths={checked()} />)
    fireEvent.change(screen.getByLabelText('Adjustment'), { target: { value: 'mean' } })
    fireEvent.change(screen.getByLabelText('Subgroup'), { target: { value: 'timing=BMO' } })
    expect(screen.getByRole('img', { name: 'Mean abnormal log IV path with its pointwise 95% band, mean-adjusted, subgroup BMO' })).toBeInTheDocument()
    const d = mean('mean-line')
    expect(count(d, 'M')).toBe(1)
    expect(xsOf(d)).toEqual(XS)
    expect(new Set(ys(d)).size).toBe(1) // a constant mean is a horizontal line
    expect(count(mean('mean-band'), 'Z')).toBe(1) // no gap in this series
  })
  it('shows the numbers of the selected series as given, with null as a dash (day 0 has no mean in market / all)', () => {
    render(<CrushPathsDisplay paths={checked()} />)
    const table = screen.getByRole('table', { name: 'Mean path numbers', hidden: true })
    const rows = within(table).getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell').map((c) => c.textContent))
    expect(rows).toEqual([
      ['-2', '3', '0.5', '0.25', '0.75'],
      ['-1', '3', '1', '0.75', '1.25'],
      ['0', '—', '—', '—', '—'],
      ['1', '3', '2', '1.75', '2.25'],
      ['2', '3', '2.5', '2.25', '2.75'],
    ])
    fireEvent.change(screen.getByLabelText('Subgroup'), { target: { value: 'timing=AMC' } })
    const amc = within(screen.getByRole('table', { name: 'Mean path numbers', hidden: true })).getAllByRole('row')[1]
    expect(within(amc).getAllByRole('cell').map((c) => c.textContent)).toEqual(['-2', '3', '0', '-0.5', '0.5']) // mean 0 is shown as 0, not as a dash
  })
  it('draws no day-0 marker when the window has no day 0, and still draws the paths', () => {
    // days -2, -1, 1, 2: drop the day-0 entry from every array
    const without0 = (a: unknown[]) => a.filter((_, i) => i !== 2)
    const data = {
      ...EVENT_PATHS_DATA_FIXTURE,
      rel_days: without0(EVENT_PATHS_DATA_FIXTURE.rel_days),
      series: EVENT_PATHS_DATA_FIXTURE.series.map((s) => ({ ...s, n: without0(s.n), mean: without0(s.mean), ci_lo: without0(s.ci_lo), ci_hi: without0(s.ci_hi) })),
      per_event: EVENT_PATHS_DATA_FIXTURE.per_event.map((e) => ({ ...e, values: without0(e.values) })),
    }
    setReducedMotion(true)
    const { container } = render(<CrushPathsDisplay paths={checked(data)} />)
    expect(container.querySelector('.day0-line')).toBeNull()
    expect(container.querySelectorAll('path[data-event]')).toHaveLength(3)
  })
  it('draws the day-0 marker when the window has a day 0', () => {
    setReducedMotion(true)
    const { container } = render(<CrushPathsDisplay paths={checked()} />)
    expect(container.querySelectorAll('.day0-line')).toHaveLength(2) // one per chart
  })
  it('falls back to the first adjustment and subgroup of a newly loaded file that lacks the chosen ones', () => {
    setReducedMotion(true)
    const { rerender } = render(<CrushPathsDisplay paths={checked()} />)
    fireEvent.change(screen.getByLabelText('Adjustment'), { target: { value: 'mean' } })
    fireEvent.change(screen.getByLabelText('Subgroup'), { target: { value: 'timing=BMO' } })
    // a new file with only (market, all)
    const onlyMarketAll = edited(EVENT_PATHS_DATA_FIXTURE, ['series'], [EVENT_PATHS_DATA_FIXTURE.series[0]])
    rerender(<CrushPathsDisplay paths={checked(onlyMarketAll)} />)
    expect(screen.getByLabelText('Adjustment')).toHaveValue('market')
    expect(screen.getByLabelText('Subgroup')).toHaveValue('all=all')
    expect(screen.getByRole('img', { name: /market-adjusted, subgroup all/ })).toBeInTheDocument()
  })
  it('says so, and draws no mean chart, when the file has no series for the chosen adjustment and subgroup', () => {
    // only (market, all) and (mean, BMO): the pair (market, BMO) does not exist
    const data = edited(EVENT_PATHS_DATA_FIXTURE, ['series'], [EVENT_PATHS_DATA_FIXTURE.series[0], EVENT_PATHS_DATA_FIXTURE.series[4]])
    render(<CrushPathsDisplay paths={checked(data)} />)
    fireEvent.change(screen.getByLabelText('Subgroup'), { target: { value: 'timing=BMO' } })
    expect(screen.getByText('The file has no series for market-adjusted values in subgroup BMO.')).toBeInTheDocument()
    expect(screen.queryByTestId('mean-line')).toBeNull()
    expect(screen.queryByRole('img', { name: /Mean abnormal log IV path/ })).toBeNull()
  })
})

describe('CrushPathsDisplay: per-event paths, animated', () => {
  it('draws one path per event with a title naming ticker, day 0 and timing', () => {
    setReducedMotion(true)
    const { container } = render(<CrushPathsDisplay paths={checked()} />)
    expect(eventPaths(container).map(([id]) => id)).toEqual(['FXA:2031-01-02', 'FXB:2031-01-09', 'FXA:2031-04-03'])
    expect(screen.getByText('FXA 2031-01-03 (BMO)')).toBeInTheDocument()
    expect(screen.getByText('FXB 2031-01-10 (AMC)')).toBeInTheDocument()
  })
  it('labels an event without a timing as such', () => {
    setReducedMotion(true)
    render(<CrushPathsDisplay paths={checked(edited(EVENT_PATHS_DATA_FIXTURE, ['per_event', 0, 'timing_used'], null))} />)
    expect(screen.getByText('FXA 2031-01-03 (timing unknown)')).toBeInTheDocument()
  })
  it('autoplays when motion is allowed: starts at the first day, one point per path, and offers Pause', () => {
    setReducedMotion(false)
    vi.useFakeTimers()
    const { container } = render(<CrushPathsDisplay paths={checked()} />)
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument()
    expect(screen.getByText('Showing event days -2 to -2')).toBeInTheDocument()
    // frame 0: every path is a single point at the first day, drawn as a dot ("h0")
    for (const [, d] of eventPaths(container)) {
      expect(d).toMatch(/^M56 [\d.]+h0$/)
    }
  })
  it('reveals one more day per frame: after 1, 2, 3 and 4 ticks the paths have 2, 3, 4 and 5 points', () => {
    setReducedMotion(false)
    vi.useFakeTimers()
    const { container } = render(<CrushPathsDisplay paths={checked()} />)
    const E1 = () => eventPaths(container)[0][1] // E1 has no null: [1, 2, 3, 4, 5]
    tick()
    expect(xsOf(E1())).toEqual(XS.slice(0, 2))
    expect(screen.getByText('Showing event days -2 to -1')).toBeInTheDocument()
    tick()
    expect(xsOf(E1())).toEqual(XS.slice(0, 3))
    tick()
    expect(xsOf(E1())).toEqual(XS.slice(0, 4))
    tick()
    expect(xsOf(E1())).toEqual(XS)
    expect(screen.getByText('Showing event days -2 to 2')).toBeInTheDocument()
  })
  it('breaks a path at a missing day: E2 [0, 1, null, 3, 4] has two runs once day 1 is reached, never a 0 at day 0', () => {
    setReducedMotion(false)
    vi.useFakeTimers()
    const { container } = render(<CrushPathsDisplay paths={checked()} />)
    const E2 = () => eventPaths(container)[1][1]
    tick(2) // frame 2 = day 0: still only days -2, -1 (day 0 is null)
    expect(count(E2(), 'M')).toBe(1)
    expect(xsOf(E2())).toEqual(XS.slice(0, 2))
    tick(2) // frame 4 = day 2: days 1, 2 form a second run
    expect(count(E2(), 'M')).toBe(2)
    expect(xsOf(E2())).toEqual([XS[0], XS[1], XS[3], XS[4]])
  })
  it('stops by itself on the last frame and then offers Play; the next tick changes nothing', () => {
    setReducedMotion(false)
    vi.useFakeTimers()
    const { container } = render(<CrushPathsDisplay paths={checked()} />)
    tick(4)
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument() // on the last frame, one more tick stops it
    tick()
    expect(screen.getByRole('button', { name: 'Play' })).toBeInTheDocument()
    const before = eventPaths(container)
    tick(10)
    expect(eventPaths(container)).toEqual(before)
    expect(vi.getTimerCount()).toBe(0)
  })
  it('Pause stops the animation where it is, and Play resumes it', () => {
    setReducedMotion(false)
    vi.useFakeTimers()
    const { container } = render(<CrushPathsDisplay paths={checked()} />)
    tick()
    fireEvent.click(screen.getByRole('button', { name: 'Pause' }))
    expect(screen.getByRole('button', { name: 'Play' })).toBeInTheDocument()
    expect(vi.getTimerCount()).toBe(0)
    const paused = eventPaths(container)
    tick(5)
    expect(eventPaths(container)).toEqual(paused)
    expect(xsOf(paused[0][1])).toEqual(XS.slice(0, 2))
    fireEvent.click(screen.getByRole('button', { name: 'Play' }))
    tick()
    expect(xsOf(eventPaths(container)[0][1])).toEqual(XS.slice(0, 3))
  })
  it('Play after the animation finished starts it again from the first day', () => {
    setReducedMotion(false)
    vi.useFakeTimers()
    const { container } = render(<CrushPathsDisplay paths={checked()} />)
    tick(5)
    fireEvent.click(screen.getByRole('button', { name: 'Play' }))
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument()
    expect(eventPaths(container)[0][1]).toMatch(/^M56 [\d.]+h0$/)
  })
  it('has a slider that jumps to a day and pauses', () => {
    setReducedMotion(false)
    vi.useFakeTimers()
    const { container } = render(<CrushPathsDisplay paths={checked()} />)
    const slider = screen.getByLabelText('Event day shown')
    expect(slider).toHaveAttribute('min', '0')
    expect(slider).toHaveAttribute('max', '4')
    fireEvent.change(slider, { target: { value: '3' } })
    expect(slider).toHaveValue('3')
    expect(screen.getByText('Showing event days -2 to 1')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Play' })).toBeInTheDocument()
    expect(xsOf(eventPaths(container)[0][1])).toEqual(XS.slice(0, 4))
    tick(3)
    expect(xsOf(eventPaths(container)[0][1])).toEqual(XS.slice(0, 4)) // paused: nothing moved
  })
  it('follows the slider while playing: the slider moves with the frames', () => {
    setReducedMotion(false)
    vi.useFakeTimers()
    render(<CrushPathsDisplay paths={checked()} />)
    expect(screen.getByLabelText('Event day shown')).toHaveValue('0')
    tick(2)
    expect(screen.getByLabelText('Event day shown')).toHaveValue('2')
  })

  it('does NOT autoplay under prefers-reduced-motion: shows the finished picture, offers Play, and no timer runs', () => {
    setReducedMotion(true)
    vi.useFakeTimers()
    const { container } = render(<CrushPathsDisplay paths={checked()} />)
    expect(screen.getByRole('button', { name: 'Play' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Pause' })).toBeNull()
    expect(screen.getByText('Showing event days -2 to 2')).toBeInTheDocument()
    expect(xsOf(eventPaths(container)[0][1])).toEqual(XS)
    expect(vi.getTimerCount()).toBe(0)
    const before = eventPaths(container)
    tick(20)
    expect(eventPaths(container)).toEqual(before)
  })
  it('treats an unknown motion preference (no matchMedia) as reduced motion', () => {
    setReducedMotion(undefined)
    vi.useFakeTimers()
    render(<CrushPathsDisplay paths={checked()} />)
    expect(screen.getByRole('button', { name: 'Play' })).toBeInTheDocument()
    expect(vi.getTimerCount()).toBe(0)
  })
  it('under reduced motion, Play still works when the visitor asks for it (it replays from the first day)', () => {
    setReducedMotion(true)
    vi.useFakeTimers()
    const { container } = render(<CrushPathsDisplay paths={checked()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Play' }))
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument()
    expect(eventPaths(container)[0][1]).toMatch(/^M56 [\d.]+h0$/)
    tick()
    expect(xsOf(eventPaths(container)[0][1])).toEqual(XS.slice(0, 2))
  })
  it('clears its timer when the page goes away', () => {
    setReducedMotion(false)
    vi.useFakeTimers()
    const { unmount } = render(<CrushPathsDisplay paths={checked()} />)
    expect(vi.getTimerCount()).toBe(1)
    unmount()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('draws the mean-adjusted mean path of the subgroup on top, revealed with the same frames', () => {
    setReducedMotion(false)
    vi.useFakeTimers()
    render(<CrushPathsDisplay paths={checked()} />)
    // (mean, all) = [1, 2, 3, 2, 1]
    expect(xsOf(mean('animated-mean'))).toEqual([XS[0]])
    tick(2)
    expect(xsOf(mean('animated-mean'))).toEqual(XS.slice(0, 3))
  })
  it('filters the event paths by the subgroup: BMO has 2 events, AMC has 1', () => {
    setReducedMotion(true)
    const { container } = render(<CrushPathsDisplay paths={checked()} />)
    fireEvent.change(screen.getByLabelText('Subgroup'), { target: { value: 'timing=BMO' } })
    expect(eventPaths(container).map(([id]) => id)).toEqual(['FXA:2031-01-02', 'FXA:2031-04-03'])
    fireEvent.change(screen.getByLabelText('Subgroup'), { target: { value: 'timing=AMC' } })
    expect(eventPaths(container).map(([id]) => id)).toEqual(['FXB:2031-01-09'])
  })
  it('starts the animation over when the subgroup changes', () => {
    setReducedMotion(false)
    vi.useFakeTimers()
    const { container } = render(<CrushPathsDisplay paths={checked()} />)
    tick(5) // finished
    expect(screen.getByRole('button', { name: 'Play' })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Subgroup'), { target: { value: 'timing=BMO' } })
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument()
    expect(eventPaths(container)[0][1]).toMatch(/^M56 [\d.]+h0$/)
  })
  it('does not restart the animation when only the adjustment changes (it only affects the mean chart)', () => {
    setReducedMotion(false)
    vi.useFakeTimers()
    const { container } = render(<CrushPathsDisplay paths={checked()} />)
    tick(2)
    fireEvent.change(screen.getByLabelText('Adjustment'), { target: { value: 'mean' } })
    expect(xsOf(eventPaths(container)[0][1])).toEqual(XS.slice(0, 3))
  })
  it('draws the event paths without a mean overlay when the file has no mean-adjusted series for the subgroup', () => {
    setReducedMotion(true)
    // keep (market, all) and (market, BMO) only: there is no (mean, ...) series at all
    const data = edited(EVENT_PATHS_DATA_FIXTURE, ['series'], EVENT_PATHS_DATA_FIXTURE.series.slice(0, 2))
    const { container } = render(<CrushPathsDisplay paths={checked(data)} />)
    expect(screen.queryByTestId('animated-mean')).toBeNull()
    expect(eventPaths(container)).toHaveLength(3)
  })
  it('says so when the file has no events in the subgroup, and offers no Play button for them', () => {
    setReducedMotion(true)
    render(<CrushPathsDisplay paths={checked(edited(EVENT_PATHS_DATA_FIXTURE, ['per_event'], []))} />)
    expect(screen.getByText('The file has no per-event paths for subgroup all.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Play' })).toBeNull()
  })
  it('says so for a subgroup the events cannot be filtered by', () => {
    setReducedMotion(true)
    const series = EVENT_PATHS_DATA_FIXTURE.series.map((s) => ({ ...s, subgroup_key: 'sector', subgroup_value: 'Fixture Sector One' }))
    render(<CrushPathsDisplay paths={checked(edited(EVENT_PATHS_DATA_FIXTURE, ['series'], [series[0], { ...series[3] }]))} />)
    expect(screen.getByText('The file has no per-event paths for subgroup Fixture Sector One.')).toBeInTheDocument()
  })
  it('gives the chart a name that says how many events and which days are drawn', () => {
    setReducedMotion(true)
    render(<CrushPathsDisplay paths={checked()} />)
    expect(screen.getByRole('img', { name: 'Per-event abnormal log IV paths, 3 events, event days -2 to 2' })).toBeInTheDocument()
  })
  it('says the event paths are mean-adjusted (the file has no market-adjusted path per event)', () => {
    setReducedMotion(true)
    render(<CrushPathsDisplay paths={checked()} />)
    expect(screen.getByText(/mean-adjusted \(the file has no market-adjusted path per event\)/)).toBeInTheDocument()
  })
})
