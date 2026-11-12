import { describe, expect, it } from 'vitest'
import { summarizeTrend } from './trendSummary'

const now = new Date('2026-11-02T12:00:00')

describe('summarizeTrend', () => {
  it('does not mix distinct instruments or unidentified rows in the trend average', () => {
    const result = summarizeTrend(
      [
        { date_key: '2026-10-30', test_type: 'SAS', index: 10 },
        { date_key: '2026-10-31', test_type: 'SDS', index: 60 },
        { date_key: '2026-11-01', test_type: 'SDS', index: 80 },
        { date_key: '2026-11-02', index: 20 },
      ],
      7,
      now,
    )
    expect(result.instrument).toBe('SDS')
    expect(result.sampleCount).toBe(2)
    expect(result.mean).toBe(70)
    expect(result.change).toBe(20)
  })
  it('reads the backend date_key contract and does not guess a year from short labels', () => {
    const result = summarizeTrend(
      [
        { date: '11-01', date_key: '2026-11-01', test_type: 'SDS', index: 60 },
        { date: '11-02', date_key: '2026-11-02', test_type: 'SDS', index: 70 },
        { date: '10-31', test_type: 'SDS', index: 80 },
        { date_key: '2026-11-02', test_type: 'SDS', index: -1 },
        { date_key: '2026-11-02', test_type: 'SDS', index: 101 },
      ],
      7,
      now,
    )
    expect(result.sampleCount).toBe(2)
    expect(result.mean).toBe(65)
    expect(result.change).toBe(10)
    expect(result.points.at(-1)).toEqual({ date: '2026-11-02', value: 70 })
    expect(
      summarizeTrend([{ date_key: '2026-11-02', test_type: 'SDS', index: 70 }], 7, now).change,
    ).toBeNull()
    expect(summarizeTrend([{ date_key: '2026-11-02', index: 70 }], 7, now).sampleCount).toBe(0)
  })
  it('sorts dates, uses the last valid same-day value, and keeps real zeroes', () => {
    const result = summarizeTrend(
      [
        { date: '2026-11-02', test_type: 'SDS', index: '0' },
        { date: '2026-11-01', test_type: 'SDS', index: 12 },
        { date: '2026-11-02', test_type: 'SDS', index: '' },
        { date: '2026-11-02', test_type: 'SDS', index: 8 },
      ],
      7,
      now,
    )

    expect(result.sampleCount).toBe(2)
    expect(result.first).toEqual({ date: '2026-11-01', value: 12 })
    expect(result.last).toEqual({ date: '2026-11-02', value: 8 })
    expect(result.change).toBe(-4)
    expect(result.mean).toBe(10)
    expect(result.points.slice(-2)).toEqual([
      { date: '2026-11-01', value: 12 },
      { date: '2026-11-02', value: 8 },
    ])
  })

  it('keeps missing dates as null gaps and excludes null, blank, invalid, and out-of-window values', () => {
    const result = summarizeTrend(
      [
        { date: '2026-10-26', test_type: 'SDS', index: 4 }, // outside the inclusive 7-day window
        { date: '2026-10-28', test_type: 'SDS', index: 0 },
        { date: '2026-10-29', test_type: 'SDS', index: null },
        { date: '2026-10-30', test_type: 'SDS', index: ' ' },
        { date: '2026-10-31', test_type: 'SDS', index: 'bad' },
        { date: '2026-11-02', test_type: 'SDS', index: 10 },
      ],
      7,
      now,
    )

    expect(result.sampleCount).toBe(2)
    expect(result.mean).toBe(5)
    expect(result.min).toBe(0)
    expect(result.max).toBe(10)
    expect(result.points.map((point) => point.value)).toEqual([null, 0, null, null, null, null, 10])
  })

  it('uses the requested calendar window and returns an empty summary without inventing values', () => {
    const result = summarizeTrend(
      [
        { date: '2026-08-04', test_type: 'SDS', index: 3 },
        { date: '2026-08-05', test_type: 'SDS', index: 30 },
        { date: '2026-11-03', test_type: 'SDS', index: 99 },
      ],
      90,
      now,
    )

    expect(result.days).toBe(90)
    expect(result.sampleCount).toBe(1)
    expect(result.points).toHaveLength(90)
    expect(result.first).toEqual({ date: '2026-08-05', value: 30 })

    const empty = summarizeTrend([{ date: '2026-11-02', test_type: 'SDS', index: null }], 7, now)
    expect(empty.sampleCount).toBe(0)
    expect(empty.mean).toBeNull()
    expect(empty.change).toBeNull()
    expect(empty.points.every((point) => point.value === null)).toBe(true)
  })
})
