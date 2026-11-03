/**
 * 鹅直播跳转 path 拼装。
 *
 * 唯一入口：pages/webView/webView?appId=<店铺 app_id>&aliveId=<直播间 id>&ko_token=<店铺登录态>
 * 直播、录播、回放都是同一个路径；ko_token 必传 —— 不带会走新用户注册，身份与品牌侧不一致。
 */

export const PAGE_PATH = 'pages/webView/webView'

export interface BuildPathOptions {
  appId: string
  aliveId: string
  /** 店铺级登录态（必传；空则抛错，不允许无 token 跳转） */
  koToken: string
  /** 分享人 user_id（可空） */
  shareUserId?: string
}

/**
 * 拼装跳转 path。
 * 规则：值一律 encodeURIComponent；缺 appId / aliveId / koToken 直接抛错（不带着坏参数去跳）。
 */
export function buildLivePath(options: BuildPathOptions): string {
  const appId = String(options?.appId || '').trim()
  const aliveId = String(options?.aliveId || '').trim()
  const koToken = String(options?.koToken || '').trim()
  if (!appId || !aliveId) throw new Error('缺少 appId 或 aliveId')
  if (!koToken) throw new Error('缺少 ko_token（必须先登录，且登录店铺与目标店铺一致）')

  const pairs = [
    'appId=' + encodeURIComponent(appId),
    'aliveId=' + encodeURIComponent(aliveId),
    'ko_token=' + encodeURIComponent(koToken),
  ]

  const shareUserId = String(options?.shareUserId || '').trim()
  if (shareUserId) pairs.push('share_user_id=' + encodeURIComponent(shareUserId))

  return PAGE_PATH + '?' + pairs.join('&')
}

export interface KoTokenDecision {
  koToken: string
  /** true 才能跳：已登录 + 店铺一致 + 本地 token 未过期 */
  ok: boolean
  reason: string
}

/**
 * 判断这次跳转能否进行（ko_token 必传，所以不满足条件的跳转直接拦下）。
 * ko_token 是**店铺级**的，目标店铺与登录店铺不同时不能用，否则身份会对错。
 */
export function decideKoToken(params: {
  loginStoreAppId: string
  targetStoreAppId: string
  koToken?: string
  sessionValid: boolean
}): KoTokenDecision {
  const loginStore = String(params.loginStoreAppId || '').trim()
  const targetStore = String(params.targetStoreAppId || '').trim()
  const token = String(params.koToken || '').trim()

  if (!params.sessionValid) return { koToken: '', ok: false, reason: '未登录：ko_token 必传，请先登录' }
  if (!loginStore || !targetStore || loginStore !== targetStore) {
    return { koToken: '', ok: false, reason: '登录店铺与目标店铺不同：ko_token 是店铺级，不能跳转' }
  }
  if (!token) return { koToken: '', ok: false, reason: '本地 ko_token 已过期：请重新登录再跳' }
  return { koToken: token, ok: true, reason: '将携带 ko_token（归属店铺 ' + loginStore + '）' }
}

