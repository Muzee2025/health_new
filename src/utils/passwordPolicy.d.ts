/**
 * `passwordPolicy.js` 的类型声明。
 * 该模块是纯函数，校验新账号密码策略；返回空字符串表示通过。
 */
export function passwordPolicyError(password: unknown): string
