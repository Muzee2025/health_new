export const ASSESSMENT_DRAFT_VERSION = 2
export const ASSESSMENT_DRAFT_TTL_MS = 24 * 60 * 60 * 1000

export function createSubmissionId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (char) => {
    const value = Math.floor(Math.random() * 16)
    return (char === 'x' ? value : (value & 0x3) | 0x8).toString(16)
  })
}

export function buildAssessmentSubmission(testId, answers, submissionId) {
  return {
    test_type: testId,
    answers: Object.fromEntries(answers.map((value, index) => [String(index), value])),
    submission_id: submissionId,
  }
}

export function matchesAssessmentResult(result, testId) {
  return Boolean(result && (result.test_id ?? result.id) && result.test_type === testId)
}

export function isValidAssessmentDraft(draft, { identity, test, now = Date.now() }) {
  if (!draft || !identity || !test) return false
  if (
    draft.version !== ASSESSMENT_DRAFT_VERSION ||
    draft.identity !== identity ||
    draft.testId !== test.id
  )
    return false
  if (typeof draft.submissionId !== 'string' || draft.submissionId.length < 16) return false
  if (
    !Number.isFinite(draft.savedAt) ||
    now < draft.savedAt ||
    now - draft.savedAt > ASSESSMENT_DRAFT_TTL_MS
  )
    return false
  if (!Array.isArray(draft.answers) || draft.answers.length !== test.questions.length) return false
  return draft.answers.every(
    (answer, index) =>
      answer == null ||
      test.questions[index].options?.some((option) => option.val === answer) ||
      test.options?.some((option) => option.val === answer),
  )
}
