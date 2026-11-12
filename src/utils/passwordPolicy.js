// Mirrors the new-account policy; existing accounts can still use the login form.
export function passwordPolicyError(password) {
  const value = String(password || '')
  if (
    Array.from(value).length < 8 ||
    new TextEncoder().encode(value).length > 72 ||
    !/[A-Za-z]/.test(value) ||
    !/[0-9]/.test(value)
  ) {
    return '密码至少8个字符、最多72个UTF-8字节，且包含字母和数字'
  }
  return ''
}
