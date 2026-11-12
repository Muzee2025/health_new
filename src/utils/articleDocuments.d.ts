/**
 * `articleDocuments.js` 的类型声明。
 */

/** 命中受保护的教师文档端点时返回 pathname，否则返回 null。 */
export function protectedDocumentPath(href: string | null, origin?: string): string | null

/** 拦截受保护文档的点击并触发下载；非受保护链接不处理。 */
export function downloadArticleDocument(event: MouseEvent): Promise<void>
