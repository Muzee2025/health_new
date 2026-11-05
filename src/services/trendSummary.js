const DAY_MS = 24 * 60 * 60 * 1000

function parseDay(value) {
  if (typeof value !== 'string' || !value.trim()) return null
  const match = value.trim().match(/^(\d{4})-(\d{2})-(\d{2})(?:$|[T ])/)
  if (!match) return null
  const [, yearText, monthText, dayText] = match
  const year = Number(yearText)
  const month = Number(monthText)
  const day = Number(dayText)
  const time = Date.UTC(year, month - 1, day)
  const parsed = new Date(time)
  if (parsed.getUTCFullYear() !== year || parsed.getUTCMonth() !== month - 1 || parsed.getUTCDate() !== day) return null
  return { key: `${yearText}-${monthText}-${dayText}`, time }
}

function parseIndex(value) {
  if (typeof value === 'string' && !value.trim()) return null
  if (typeof value !== 'string' && typeof value !== 'number') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed >= 0 && parsed <= 100 ? parsed : null
}

function localDayStart(value) {
  const date = value instanceof Date ? value : new Date(value)
  return Date.UTC(date.getFullYear(), date.getMonth(), date.getDate())
}

/**
 * Summarize recorded trend values in an inclusive calendar-day window.
 * Duplicate dates use the last valid value in API order; absent/invalid values
 * never replace a valid value and are never treated as zero.
 */
export function summarizeTrend(records, days = 30, now = new Date()) {
  const windowDays = [7, 30, 90].includes(Number(days)) ? Number(days) : 30
  const end = localDayStart(now)
  const start = end - (windowDays - 1) * DAY_MS
  const byDate = new Map()
  const candidates = []

  for (const record of Array.isArray(records) ? records : []) {
    const date = parseDay(record?.date_key) || parseDay(record?.date)
    const value = parseIndex(record?.index)
    if (!date || value === null || date.time < start || date.time > end) continue
    candidates.push({ date, value, instrument: ['SDS', 'SAS'].includes(record?.test_type) ? record.test_type : null })
  }
  // SDS and SAS describe different constructs. Use the latest identified tool,
  // rather than mixing their values in a single average or daily trend.
  const identified = candidates.filter(item => item.instrument).sort((a, b) => a.date.time - b.date.time)
  const instrument = identified.at(-1)?.instrument || null
  for (const item of candidates) {
    if (!instrument || item.instrument !== instrument) continue
    byDate.set(item.date.key, item.value)
  }

  const observations = [...byDate.entries()]
    .map(([date, value]) => ({ date, value, time: parseDay(date).time }))
    .sort((left, right) => left.time - right.time)
  const values = observations.map(item => item.value)
  const mean = values.length ? values.reduce((total, value) => total + value, 0) / values.length : null
  const first = observations[0] ?? null
  const last = observations.at(-1) ?? null
  const dailyPoints = []
  for (let time = start; time <= end; time += DAY_MS) {
    const date = new Date(time).toISOString().slice(0, 10)
    dailyPoints.push({ date, value: byDate.has(date) ? byDate.get(date) : null })
  }

  return {
    days: windowDays,
    instrument,
    sampleCount: observations.length,
    mean: mean === null ? null : Number(mean.toFixed(1)),
    first: first ? { date: first.date, value: first.value } : null,
    last: last ? { date: last.date, value: last.value } : null,
    change: observations.length >= 2 ? Number((last.value - first.value).toFixed(1)) : null,
    min: values.length ? Math.min(...values) : null,
    max: values.length ? Math.max(...values) : null,
    points: dailyPoints,
  }
}
