/**
 * 本地登录态（ko_token / user_id / 过期时间）。
 *
 * uni 用全局 `uni` 对象（H5 与小程序一致），为了能在 node 里跑断言，
 * 这里只通过 getUni() 取一次，测试时可以塞一个 stub。
 */

export const STORAGE_KEYS = {
  token: 'ko_token',
  userId: 'user_id',
  expiresAt: 'ko_token_expires_at',
  anonyToken: 'anony_token',
  /** 完整登录数据（LOGIN_DATA） */
  loginData: 'LOGIN_DATA',
  /** 店铺 ID（APPID） */
  appId: 'APPID',
  /** 微信头像昵称缓存 */
  wxUserProfile: 'wx_user_profile',
}

export interface Session {
  token: string
  userId: string
  expiresAt: number
  valid: boolean
}

type Store = {
  get(key: string): string
  set(key: string, value: unknown): void
  remove(key: string): void
}

const memory = new Map<string, string>()

/**
 * 选择存储实现（每次调用时解析，避免模块加载期拿不到平台 API）：
 *   1. 小程序：全局 uni 的同步存储
 *   2. H5：localStorage（H5 构建里全局 uni 不一定带存储 API）
 *   3. 兜底：内存（node 里跑断言时用）
 */
function resolveStore(): Store {
  const u = (globalThis as any).uni
  if (u && typeof u.getStorageSync === 'function') {
    return {
      get: (key) => u.getStorageSync(key),
      set: (key, value) => u.setStorageSync(key, value),
      remove: (key) => u.removeStorageSync(key),
    }
  }
  const ls = (globalThis as any).localStorage
  if (ls && typeof ls.getItem === 'function') {
    return {
      get: (key) => ls.getItem(key),
      set: (key, value) => ls.setItem(key, typeof value === 'string' ? value : JSON.stringify(value)),
      remove: (key) => ls.removeItem(key),
    }
  }
  return {
    get: (key) => (memory.has(key) ? memory.get(key) : ''),
    set: (key, value) => memory.set(key, typeof value === 'string' ? value : JSON.stringify(value)),
    remove: (key) => memory.delete(key),
  }
}

function read(key: string): string {
  const raw = readRaw(key)
  if (raw === undefined || raw === null) return ''
  return typeof raw === 'string' ? raw : JSON.stringify(raw)
}

function readRaw(key: string): unknown {
  try {
    return resolveStore().get(key)
  } catch {
    return ''
  }
}

function readJson(key: string): any {
  const raw = readRaw(key)
  if (!raw) return null
  if (typeof raw !== 'string') return raw
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

function write(key: string, value: unknown): void {
  try {
    resolveStore().set(key, value)
  } catch {
    /* 忽略存储失败 */
  }
}

function remove(key: string): void {
  try {
    resolveStore().remove(key)
  } catch {
    /* 忽略 */
  }
}

export function clearSession(): void {
  remove(STORAGE_KEYS.token)
  remove(STORAGE_KEYS.userId)
  remove(STORAGE_KEYS.expiresAt)
  // 登录数据随会话失效；APPID 是环境配置，保留
  remove(STORAGE_KEYS.loginData)
}

/** 保存登录态；token 或 userId 缺失时视为登出 */
export function saveSession(session: { token?: string; userId?: string; expiresIn?: number; appId?: string }): void {
  const token = String(session?.token || '')
  const userId = String(session?.userId || '')
  if (!token || !userId) {
    clearSession()
    return
  }
  write(STORAGE_KEYS.token, token)
  write(STORAGE_KEYS.userId, userId)
  if (session?.appId) write(STORAGE_KEYS.appId, String(session.appId))
  // LOGIN_DATA 结构：{ user_id, app_id, token }
  write(STORAGE_KEYS.loginData, {
    user_id: userId,
    app_id: String(session?.appId || read(STORAGE_KEYS.appId) || ''),
    token,
  })
  const expiresIn = Number(session?.expiresIn) || 0
  if (expiresIn > 0) {
    write(STORAGE_KEYS.expiresAt, Date.now() + expiresIn * 1000)
  } else {
    remove(STORAGE_KEYS.expiresAt)
  }
}

/** 冷启动清理：本地已明确过期就清掉，避免用过期凭证发请求 */
export function clearExpiredSession(): boolean {
  const expiresAt = Number(read(STORAGE_KEYS.expiresAt)) || 0
  if (!expiresAt || expiresAt > Date.now()) return false
  clearSession()
  return true
}

/** 读登录态；半残（只有 token 或只有 userId）会自愈清理 */
export function getSession(): Session {
  const token = read(STORAGE_KEYS.token)
  const userId = read(STORAGE_KEYS.userId)
  const expiresAt = Number(read(STORAGE_KEYS.expiresAt)) || 0

  if (token && userId) return { token, userId, expiresAt, valid: true }
  if (token || userId) clearSession()
  return { token: '', userId: '', expiresAt: 0, valid: false }
}

/** 本地未过期的 ko_token；过期或未登录返回空串 */
export function getFreshKoToken(): string {
  const session = getSession()
  if (!session.token) return ''
  if (session.expiresAt && session.expiresAt <= Date.now()) return ''
  return session.token
}

/** 人类可读的过期时间 */
export function formatExpiresAt(expiresAt: number): string {
  if (!expiresAt) return '-'
  const d = new Date(expiresAt)
  const pad = (n: number) => (n < 10 ? '0' + n : String(n))
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes())
}

/** 缓存微信头像昵称（wx_user_profile） */
export function saveWxUserProfile(profile: { nickname?: string; avatar?: string }): void {
  write(STORAGE_KEYS.wxUserProfile, { nickname: String(profile?.nickname || ''), avatar: String(profile?.avatar || '') })
}

/** 读缓存的微信头像昵称 */
export function getWxUserProfile(): { nickname: string; avatar: string } {
  const data = readJson(STORAGE_KEYS.wxUserProfile)
  return { nickname: String(data?.nickname || ''), avatar: String(data?.avatar || '') }
}

/** 读完整登录数据（LOGIN_DATA） */
export function getLoginData(): { user_id: string; app_id: string; token: string } {
  const data = readJson(STORAGE_KEYS.loginData)
  return { user_id: String(data?.user_id || ''), app_id: String(data?.app_id || ''), token: String(data?.token || '') }
}
