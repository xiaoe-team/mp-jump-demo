/**
 * 后端接口封装。所有请求都经过 utils/request（域名重写 + 认证头注入 + 信封解包）。
 */
import { request } from '@/utils/request'
import { currentWxAppId, globalData } from '@/utils/config'

export interface LoginResult {
  koToken?: string
  userId?: string
  expiresIn?: number
}

export interface CheckResult {
  valid?: boolean
  userId?: string
  expiresIn?: number
  msg?: string
}

export interface ProfileResult {
  userId?: string
  isBindPhone?: boolean
  maskedPhone?: string
  nickname?: string
  avatar?: string
}

export interface BindStatusResult {
  isBindPhone?: boolean
  maskedPhone?: string
}

export interface BindPhoneResult {
  success?: boolean
  needMergeConfirm?: boolean
  maskedPhone?: string
  bindToken?: string
  expiresIn?: number
  conflictUserId?: string
  merged?: boolean
}

export interface LoginUrlResult {
  loginUrl?: string
  appId?: string
  userId?: string
  userExists?: number
}

export const api = {
  /** 登录：wx_app_id 通过接口入参传（不放请求头） */
  login: (code: string) =>
    request<LoginResult>('/api/login', {
      method: 'POST',
      data: { wx_app_id: currentWxAppId(), code },
    }),
  checkSession: (token: string) =>
    request<CheckResult>('/api/session/check', { method: 'POST', data: { token } }),
  profile: (token: string) =>
    request<ProfileResult>('/api/profile', { method: 'POST', data: { token } }),
  /** 手机号绑定状态 */
  checkBindPhone: (token: string) =>
    request<BindStatusResult>('/api/check-bind-phone', {
      method: 'POST',
      data: { token },
    }),
  /** 手机号绑定（阶段一）/ 合并确认（阶段二） */
  bindOrMergePhone: (params: { token: string; code?: string; bind_token?: string; confirm_merge?: boolean }) =>
    request<BindPhoneResult>('/api/bind-or-merge-phone', {
      method: 'POST',
      data: Object.assign({}, params),
    }),
  /** 内嵌 H5 登录态中转：wx_app_id + code + redirect_uri → 一次性 H5 登录地址 */
  loginUrl: (code: string, redirectUri: string) =>
    request<LoginUrlResult>('/api/login-url', {
      method: 'POST',
      data: { wx_app_id: currentWxAppId(), code, redirect_uri: redirectUri },
    }),
}

