import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { isRetryableHttpError, withApiRetry } from './advancedChatRetry'

describe('advancedChatRetry', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('retries transient failures with the existing 400ms and 800ms delays', async () => {
    const warning = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const request = vi
      .fn<() => Promise<string>>()
      .mockRejectedValueOnce({ response: { status: 503 } })
      .mockRejectedValueOnce({ response: { status: 429 } })
      .mockResolvedValue('ok')
    const pending = withApiRetry(request, 'fetchSessions', 2, () => true)

    await vi.advanceTimersByTimeAsync(400)
    expect(request).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(800)
    await expect(pending).resolves.toBe('ok')

    expect(request).toHaveBeenCalledTimes(3)
    expect(warning).toHaveBeenNthCalledWith(
      1,
      '[AdvancedAiChat] fetchSessions retrying',
      expect.objectContaining({ attempt: 1, waitMs: 400, status: 503 }),
    )
    expect(warning).toHaveBeenNthCalledWith(
      2,
      '[AdvancedAiChat] fetchSessions retrying',
      expect.objectContaining({ attempt: 2, waitMs: 800, status: 429 }),
    )
  })

  it('retries network errors but rejects non-retryable and aborted requests', async () => {
    expect(isRetryableHttpError(new Error('network'), () => true)).toBe(true)
    expect(isRetryableHttpError({ status: 429 }, () => true)).toBe(true)
    expect(isRetryableHttpError({ response: { status: 503 } }, () => true)).toBe(true)
    expect(isRetryableHttpError({ response: { status: 400 } }, () => true)).toBe(false)
    expect(isRetryableHttpError({ name: 'AbortError' }, () => true)).toBe(false)

    const error = { response: { status: 400 } }
    const request = vi.fn<() => Promise<never>>().mockRejectedValue(error)
    await expect(withApiRetry(request, 'badRequest', 2, () => true)).rejects.toBe(error)
    expect(request).toHaveBeenCalledTimes(1)
  })

  it('stops after the session becomes inactive', async () => {
    const request = vi.fn<() => Promise<never>>().mockRejectedValue(new Error('network'))

    await expect(withApiRetry(request, 'inactive', 2, () => false)).resolves.toBeUndefined()
    expect(request).toHaveBeenCalledTimes(1)
  })
})
