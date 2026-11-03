/**
 * 请求层：只做一件事——拼后端地址、按 {code,msg,data} 信封解包。
 *
 * 约定：**不使用任何自定义请求头**，业务参数一律走请求体
 * （wx_app_id / code / redirect_uri / token / app_env_type）。
 * 业务失败（code!==0）直接 reject，调用方按真实错误展示，不做兜底。
 */
import { globalData, isH5 } from '@/utils/config'

export interface RequestOptions {
  method?: 'GET' | 'POST'
  data?: Record<string, unknown>
  timeout?: number
}

export function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const base = globalData.API_BASE
  if (!base && !isH5()) {
    return Promise.reject(new Error('未配置 VITE_API_BASE：请在 mp-demo/.env.<mode> 里补上接口域名'))
  }

  return new Promise((resolve, reject) => {
    uni.request({
      url: base + path,
      method: options.method || 'GET',
      data: options.data || {},
      timeout: options.timeout || 15000,
      header: { 'Content-Type': 'application/json' },
      success: (res: any) => {
        const body = res?.data
        if (res.statusCode < 200 || res.statusCode >= 300 || !body || typeof body !== 'object') {
          reject(new Error((body && body.msg) || 'HTTP ' + res.statusCode))
          return
        }
        const code = Number(body.code)
        if (code !== 0) {
          reject(new Error(body.msg || '接口返回 code=' + code))
          return
        }
        resolve((body.data === null || body.data === undefined ? {} : body.data) as T)
      },
      fail: (err: any) => reject(new Error((err && err.errMsg) || '网络请求失败')),
    })
  })
}
