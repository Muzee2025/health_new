type ActiveCheck = () => boolean

type HttpErrorShape = {
  name?: string
  response?: { status?: number }
  status?: number
  message?: string
}

const asHttpError = (error: unknown): HttpErrorShape | null | undefined =>
  error as HttpErrorShape | null | undefined

export const sleep = (ms: number): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, ms))

export function isRetryableHttpError(error: unknown, isActive: ActiveCheck = () => true): boolean {
  const err = asHttpError(error)
  const status = err?.response?.status || err?.status || 0
  if (err?.name === 'AbortError' || !isActive()) return false
  if (!status) return true
  return status >= 500 || status === 429
}

export async function withApiRetry<T>(
  fn: () => Promise<T>,
  label: string,
  retries = 2,
  isActive: ActiveCheck = () => true,
): Promise<T | undefined> {
  let lastErr: unknown = null
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn()
    } catch (error) {
      if (!isActive()) return undefined
      lastErr = error
      if (!isRetryableHttpError(error, isActive) || attempt === retries) break
      const waitMs = 400 * (attempt + 1)
      const err = asHttpError(error)
      console.warn(`[AdvancedAiChat] ${label} retrying`, {
        attempt: attempt + 1,
        waitMs,
        status: err?.response?.status || err?.status,
        message: err?.message,
      })
      await sleep(waitMs)
    }
  }
  throw lastErr
}
