/**
 * 跳转参数：直播间 id 写死在前端，店铺 ID / 目标小程序 / 版本来自环境配置。
 *
 * 后端不提供、也不参与这些值——它只负责登录态（ko_token）与用户资料。
 *
 * aliveId 取法：后台打开该直播间 H5 链接
 *   https://{店铺app_id}.h5.xiaoeknow.com/v2/course/alive/<alive_id>?...
 * 里 `alive/` 后面那一段。
 */

import { globalData } from '@/utils/config'

/** 目标店铺：path 里的 appId，也是 ko_token 的归属店铺（来自 VITE_XIAOE_APP_ID） */
export const XIAOE_APP_ID_TARGET = globalData.APP_ID

/** 目标小程序：live-mp（鹅直播，来自 VITE_LIVE_MP_WX_APP_ID） */
export const LIVE_MP_WX_APP_ID = globalData.LIVE_MP_WX_APP_ID

export interface RoomConfig {
  key: string
  title: string
  desc: string
  aliveId: string
}

/** 首页两个按钮：直播 / 录播走同一个页面路径，只有 aliveId 不同 */
export const ROOMS: RoomConfig[] = [
  {
    key: "live",
    title: "进入直播",
    desc: "直播中的直播间",
    aliveId: "l_6ae8ad5be4b0694c3556835a", // 直播中的直播间
  },
  {
    key: "replay",
    title: "进入录播",
    desc: "录播 / 直播回放",
    aliveId: "l_6aab9cbbe4b0694c354a7e5a", // 录播 / 直播回放
  },
];
