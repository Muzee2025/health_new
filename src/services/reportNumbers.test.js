import { describe, expect, it } from 'vitest'
import { finiteNumberOrNull, isPresentNumber } from './reportNumbers'

describe('report measurements keep missing values separate from zero', () => {
  it('preserves gaps alongside measured points for chart series', () => {
    expect([24, null, undefined, 0, 31].map(finiteNumberOrNull)).toEqual([24, null, null, 0, 31])
  })
  it('rejects absent, invalid and boolean fields instead of drawing zero', () => {
    for (const value of [null, undefined, '', ' ', false, true, NaN, Infinity, {}, []]) {
      expect(isPresentNumber(value)).toBe(false)
    }
  })
  it('retains a genuine zero and numeric API strings', () => {
    expect(finiteNumberOrNull(0)).toBe(0)
    expect(finiteNumberOrNull('14.5')).toBe(14.5)
  })
})
