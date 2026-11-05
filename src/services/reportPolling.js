export const MAX_REPORT_POLL_ATTEMPTS = 5
export const getReportPollDelayMs = (attempt) => Math.min(1500 * (2 ** attempt), 12000)
export const shouldPollReportAgain = (attempt) => Number.isInteger(attempt) && attempt >= 0 && attempt < MAX_REPORT_POLL_ATTEMPTS
