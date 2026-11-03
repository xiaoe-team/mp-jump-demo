/**
 * 全局配置：环境变量统一收口到 globalData，
 * 页面/请求层只从 globalData 取值，不再各自读 import.meta.env。
 *
 * 页面里也可以通过 `getApp().globalData` 取到同一份配置（App.vue 已挂载）。
 *
 * 注意：不使用任何自定义请求头；小程序 appid 与店铺 ID 都作为接口入参传。
 */

const viteEnv: Record<string, any> = (import.meta as any).env || {}

function trimSlash(value: any): string {
  return String(value || '').replace(/\/+$/, '')
}

/** 后端接口地址：H5 端走同源（空串），小程序端用环境文件里的完整地址 */
function resolveApiBase(): string {
  // #ifdef H5
  return ''
  // #endif
  // #ifndef H5
  return trimSlash(viteEnv.VITE_API_BASE || '')
  // #endif
}

/** 业务 H5 / 微页面自定义域名（唯一来源，没有兜底域名） */
const H5_BASE = trimSlash(viteEnv.VITE_H5_BASE || '')
/** 内嵌 H5 演示用的课程资源 ID（形如 course_xxx） */
const H5_COURSE_ID = String(viteEnv.VITE_H5_COURSE_ID || '').trim()

export const globalData = {
  /** 环境名：development / test / production（仅排查用） */
  ENV: String(viteEnv.VITE_ENV || 'production'),
  /** 后端接口地址（H5 为空串，走同源） */
  API_BASE: resolveApiBase(),
  /** 业务 H5 / 微页面自定义域名 */
  H5_BASE,
  /** 内嵌 H5 课程资源 ID */
  H5_COURSE_ID,
  /** 小鹅通店铺 ID：跳转 path 的 appId、ko_token 归属店铺 */
  APP_ID: String(viteEnv.VITE_XIAOE_APP_ID || '').trim(),
  /** 微信小程序 appid：只取环境文件里的值，作为 wx_app_id 入参 */
  wx_app_id: String(viteEnv.VITE_WX_APP_ID || '').trim(),
  /** 内嵌环境标识：H5 侧靠它判断是否在小程序内嵌环境里 */
  APP_ENV_TYPE: 'mini_program_wechat_sdk',
  /** 跳转目标小程序（live-mp 鹅直播） */
  LIVE_MP_WX_APP_ID: String(viteEnv.VITE_LIVE_MP_WX_APP_ID || '').trim(),
}

/** 当前小程序 appid（对外统一入口；只来自环境文件，不读运行时） */
export function currentWxAppId(): string {
  return globalData.wx_app_id
}

/** 当前是否跑在 H5 端（H5 走同源，无需接口域名）。用条件编译判断，避免依赖运行时可被摇掉的 API */
export function isH5(): boolean {
  // #ifdef H5
  return true
  // #endif
  // #ifndef H5
  return false
  // #endif
}

/** 业务 H5 首页地址：只认配置的自定义域名，没有就返回空（由调用方提示去配） */
export function buildH5Url(): string {
  return globalData.H5_BASE
}

/**
 * 课程详情 H5：`{H5_BASE}/p/course/ecourse/preview/{courseId}`
 * 路径以店铺 H5 实际路由为准（课程预览页 /p/course/ecourse/preview/<课程资源ID>）；
 * 课程 H5 路径用带 preview 的正式入口：'/p/course/ecourse/preview/:courseId'。
 * 没配课程 ID 时返回空串，由调用方决定是否退回域名首页。
 */
export function buildCourseH5Url(courseId: string = globalData.H5_COURSE_ID): string {
  const id = String(courseId || '').trim()
  const base = globalData.H5_BASE
  if (!base || !id) return ''
  return base + '/p/course/ecourse/preview/' + encodeURIComponent(id)
}

/**
 * 给内嵌 H5 链接补上「小程序内嵌」标识（app_env_type，可选 app_id）。
 * H5 侧靠它判断是否在小程序内嵌环境里。
 */
export function withEmbedParams(url: string, appId?: string): string {
  const raw = String(url || '').trim()
  if (!raw) return ''

  const hashIndex = raw.indexOf('#')
  const head = hashIndex === -1 ? raw : raw.slice(0, hashIndex)
  const hash = hashIndex === -1 ? '' : raw.slice(hashIndex)
  const separator = head.indexOf('?') === -1 ? '?' : '&'
  const pieces: string[] = []

  if (!/[?&]app_env_type=/.test(head)) pieces.push('app_env_type=' + globalData.APP_ENV_TYPE)
  if (appId && !/[?&]app_id=/.test(head)) pieces.push('app_id=' + encodeURIComponent(appId))

  return pieces.length ? head + separator + pieces.join('&') + hash : raw
}

/** web-view 允许加载的域名白名单 */
export function allowedWebViewHosts(): string[] {
  const apiOrigin = (() => {
    const match = globalData.API_BASE.match(/^(https?:\/\/[^/]+)/i)
    return match ? match[1] : ''
  })()

  return [globalData.H5_BASE, apiOrigin]
    .filter(Boolean)
    .map((item) => String(item).replace(/^https?:\/\//, '').replace(/\/.*$/, ''))
}

/** 判断 web-view 目标是否在白名单内 */
export function isAllowedWebViewUrl(url: string): boolean {
  const raw = String(url || '').trim()
  if (!/^https:\/\//i.test(raw)) return false

  const host = (raw.match(/^https:\/\/([^/?#]+)/i) || [])[1] || ''
  if (!host) return false

  return allowedWebViewHosts().some((allowed) => host === allowed || host.endsWith('.' + allowed))
}
