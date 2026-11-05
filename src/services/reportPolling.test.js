import { describe, expect, it } from 'vitest'
import { MAX_REPORT_POLL_ATTEMPTS, getReportPollDelayMs, shouldPollReportAgain } from './reportPolling'

describe('report status polling', () => {
  it('backs off and stops after a fixed number of status checks', () => {
    expect([0, 1, 2, 3, 4, 5].filter(shouldPollReportAgain)).toHaveLength(MAX_REPORT_POLL_ATTEMPTS)
    expect([0, 1, 2, 3, 4, 5].map(getReportPollDelayMs)).toEqual([1500, 3000, 6000, 12000, 12000, 12000])
    expect(shouldPollReportAgain(-1)).toBe(false)
  })
})
