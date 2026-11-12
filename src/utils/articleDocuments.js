import axios from 'axios'

// Intercept only the protected document endpoint; ordinary source links keep working.
export function protectedDocumentPath(href, origin = window.location.origin) {
  try {
    const url = new URL(href, origin)
    if (url.origin !== origin) return null
    return /^\/api\/teacher\/documents\/[a-f0-9-]{32,36}\.(pdf|docx)$/i.test(url.pathname)
      ? url.pathname
      : null
  } catch {
    return null
  }
}

export async function downloadArticleDocument(event) {
  const anchor = event.target.closest?.('a[href]')
  const path = anchor && protectedDocumentPath(anchor.getAttribute('href'))
  if (!path) return
  event.preventDefault()
  const response = await axios.get(path, { responseType: 'blob' })
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = path.split('/').at(-1)
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
