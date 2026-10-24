export const writeHeaders = { 'X-Requested-With': 'qqbot-admin' }

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { cache: 'no-store', ...options })
  if (!response.ok) {
    if (response.status === 401) throw new Error('登录已失效，请刷新页面重新登录。')
    let message = response.status === 422 ? '输入不符合要求，请检查填写内容。' :
      `请求失败（${response.status}），请刷新或查看 Coolify 日志。`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') message = body.detail
    } catch { /* Proxy errors may return HTML. */ }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export function errorText(error: unknown): string {
  return error instanceof Error ? error.message : '操作失败，请刷新后重试。'
}
export function formatDate(value: string): string {
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}
