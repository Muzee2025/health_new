import { describe, expect, it } from 'vitest'
import { buildAssessmentSubmission, isValidAssessmentDraft, matchesAssessmentResult } from './assessmentFlow'

const test = {
  id: 'SDS',
  questions: [{ options: [{ val: 1 }, { val: 2 }] }, { options: [{ val: 1 }, { val: 2 }] }],
}

describe('assessment submission contract', () => {
  it('keeps raw answers and uses the existing zero-based question index', () => {
    expect(buildAssessmentSubmission('SDS', [2, 1], 'same-attempt-id')).toEqual({
      test_type: 'SDS', answers: { '0': 2, '1': 1 }, submission_id: 'same-attempt-id',
    })
  })

  it('accepts only a response for the submitted assessment type with a server ID', () => {
    expect(matchesAssessmentResult({ id: 12, test_type: 'SDS' }, 'SDS')).toBe(true)
    expect(matchesAssessmentResult({ test_id: 12, test_type: 'SAS' }, 'SDS')).toBe(false)
    expect(matchesAssessmentResult({ test_type: 'SDS' }, 'SDS')).toBe(false)
  })

  it('validates draft identity, version, expiry, and answer options', () => {
    const draft = { version: 2, identity: 'student-4', testId: 'SDS', submissionId: 'same-attempt-id-1', savedAt: 1000, answers: [2, undefined] }
    const context = { identity: 'student-4', test, now: 1500 }
    expect(isValidAssessmentDraft(draft, context)).toBe(true)
    expect(isValidAssessmentDraft({ ...draft, identity: 'other-user' }, context)).toBe(false)
    expect(isValidAssessmentDraft({ ...draft, version: 1 }, context)).toBe(false)
    expect(isValidAssessmentDraft({ ...draft, savedAt: -90000000 }, context)).toBe(false)
    expect(isValidAssessmentDraft({ ...draft, answers: [8, undefined] }, context)).toBe(false)
  })
})
