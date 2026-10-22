import { describe, expect, it } from 'vitest'
import { passwordPolicyError } from '../utils/passwordPolicy'
import { protectedDocumentPath } from '../utils/articleDocuments'

describe('new account password policy', () => {
  it('enforces codepoint length, UTF-8 upper bound, and ASCII letter and digit', () => {
    expect(passwordPolicyError('Valid123')).toBe('')
    expect(passwordPolicyError('A1短短短短短')).not.toBe('')
    expect(passwordPolicyError('A1' + '中'.repeat(24))).not.toBe('')
    expect(passwordPolicyError('A1' + '中'.repeat(23))).toBe('')
    expect(passwordPolicyError('abcdefgh')).not.toBe('')
    expect(passwordPolicyError('12345678')).not.toBe('')
  })
})

describe('protected article attachment routing', () => {
  const origin = 'https://school.example'
  const path = '/api/teacher/documents/0123456789abcdef0123456789abcdef.pdf'
  it('recognizes the exact same-origin protected path without forwarding credentials elsewhere', () => {
    expect(protectedDocumentPath(path, origin)).toBe(path)
    expect(protectedDocumentPath(origin + path, origin)).toBe(path)
    expect(protectedDocumentPath('https://other.example' + path, origin)).toBeNull()
    expect(protectedDocumentPath('javascript:alert(1)', origin)).toBeNull()
    expect(protectedDocumentPath('/api/teacher/documents/../../config.pdf', origin)).toBeNull()
    expect(protectedDocumentPath('/articles/example.pdf', origin)).toBeNull()
  })
})
