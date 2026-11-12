import { describe, expect, it } from 'vitest'
import { getFiveDimensionFailure, getFiveDimensionResult } from './fiveDimensionData'

const completePayload = {
  data_status: 'available',
  data: {
    five_dimensions: { academic: 0, interpersonal: 40, family: 60, emotion: 80, physical: 100 },
    provenance: { source: 'synthetic verified record' },
  },
}

describe('five dimension response validation', () => {
  it('accepts a complete bounded payload with provenance, including a real zero', () => {
    expect(getFiveDimensionResult(completePayload)).toEqual({
      status: 'ready',
      dimensions: { academic: 0, interpersonal: 40, family: 60, emotion: 80, physical: 100 },
      provenance: 'synthetic verified record',
    })
  })

  it('treats null and blank values as missing instead of converting them to zero', () => {
    const result = getFiveDimensionResult({
      ...completePayload,
      data: {
        ...completePayload.data,
        five_dimensions: { ...completePayload.data.five_dimensions, academic: null, family: '' },
      },
    })
    expect(result.status).toBe('partial')
    expect(result.missing).toEqual(['academic', 'family'])
    expect(result.message).toContain('学业、家庭')
  })

  it('does not plot partial or out-of-range measurements', () => {
    for (const invalidValue of [
      undefined,
      -1,
      101,
      Infinity,
      'not-a-number',
      '   ',
      '\n',
      false,
      {},
    ]) {
      const dimensions = { ...completePayload.data.five_dimensions, emotion: invalidValue }
      expect(
        getFiveDimensionResult({
          ...completePayload,
          data: { ...completePayload.data, five_dimensions: dimensions },
        }).status,
      ).toBe('partial')
    }
  })

  it('requires provenance before displaying otherwise complete dimensions', () => {
    expect(
      getFiveDimensionResult({
        ...completePayload,
        data: { five_dimensions: completePayload.data.five_dimensions },
      }),
    ).toMatchObject({ status: 'invalid' })
    expect(
      getFiveDimensionResult({
        ...completePayload,
        data: { ...completePayload.data, provenance: { source: {} } },
      }),
    ).toMatchObject({ status: 'invalid' })
  })

  it('does not treat malformed envelopes as an empty record set or override explicit missing values', () => {
    for (const payload of [
      undefined,
      null,
      {},
      { data_status: 'available', data: null },
      { data: null },
    ])
      expect(getFiveDimensionResult(payload).status).toBe('invalid')
    const dimensions = { ...completePayload.data.five_dimensions, academic: null, Academic: 80 }
    expect(
      getFiveDimensionResult({
        ...completePayload,
        data: { ...completePayload.data, five_dimensions: dimensions },
      }).status,
    ).toBe('partial')
  })

  it('distinguishes unavailable integration from an empty record set', () => {
    expect(
      getFiveDimensionResult({
        data_status: 'insufficient',
        source: 'not_available',
        message: '暂未接入',
      }),
    ).toMatchObject({ status: 'not-integrated', message: '暂未接入' })
    expect(getFiveDimensionResult({ data_status: 'empty', data: null })).toMatchObject({
      status: 'no-records',
    })
  })

  it('distinguishes an unmounted endpoint from request failures', () => {
    expect(getFiveDimensionFailure({ response: { status: 404 } }).status).toBe('not-integrated')
    expect(getFiveDimensionFailure({ code: 'ECONNABORTED' }).status).toBe('network-error')
  })
})
