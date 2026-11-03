<template>
  <!-- 交接完成前不渲染 web-view：否则会先加载裸地址（H5 立刻跳登录），
       再被换成交接地址，而交接地址里的 state 是一次性的，二次加载必失败。 -->
  <web-view v-if="ready && src" :src="src" @message="onMessage" />
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad as onPageLoad } from '@dcloudio/uni-app'
import { api } from '@/utils/api'
import { XIAOE_APP_ID_TARGET } from '@/config/live'
import { isAllowedWebViewUrl, withEmbedParams } from '@/utils/config'
import { getSession } from '@/utils/session'

/** 最终要加载的地址；交接成功是带 state 的一次性地址，失败则降级为原始地址 */
const src = ref('')
/** 只有拿到最终地址后才允许渲染 web-view（保证只加载一次） */
const ready = ref(false)
/** 是否刚从登录页回跳（query.retry=1），用于阻断登录死循环 */
let fromLogin = false

function toast(title: string) {
  uni.showToast({ title, icon: 'none' })
}

onPageLoad(async (query: Record<string, string> = {}) => {
  const raw = query.url ? decodeURIComponent(query.url) : ''
  if (!raw) {
    toast('缺少 url 参数')
    return
  }
  const target = withEmbedParams(raw, XIAOE_APP_ID_TARGET)
  if (!isAllowedWebViewUrl(target)) {
    toast('该地址不在 web-view 白名单内（需配 .env 的 VITE_H5_BASE 并加进小程序业务域名）')
    return
  }
  fromLogin = query.retry === '1'

  // 未登录先回登录页，登录完带 redirect_uri 回到本页重新走一遍交接
  if (!getSession().valid) {
    if (fromLogin) {
      toast('登录未完成，已停止自动跳转')
      return
    }
    const back = '/pages/webview/index?url=' + encodeURIComponent(target) + '&retry=1'
    uni.redirectTo({ url: '/pages/login/index?redirect_uri=' + encodeURIComponent(back) })
    return
  }

  await handover(target)
})

/**
 * 用 uni.login 的 code 换一次性登录地址（小鹅云 xe.login.url）：
 * 落地点会种下 H5 的登录 cookie，H5 才不会一直跳自己的登录页。
 * 换失败就降级加载原始地址（交给 H5 自己处理），不阻断演示。
 */
async function handover(target: string) {
  try {
    const login: any = await uni.login()
    if (!login?.code) throw new Error('uni.login 未返回 code')
    const res = await api.loginUrl(login.code, target)
    src.value = res.loginUrl || target
  } catch (error: any) {
    const msg = String((error && (error.errMsg || error.message)) || error)
    const platformLimit = /not supported|uni\.login|wx\.login|不支持/i.test(msg)
    console.warn('[webview] 换登录态失败，降级加载原地址：', msg)
    toast('换登录态失败' + (platformLimit ? '（H5 无 wx.login，请在微信小程序里试）' : ''))
    src.value = target
  } finally {
    ready.value = true
  }
}

/** H5 通过 postMessage 回传的消息（H5 侧 uni.postMessage） */
function onMessage(event: any) {
  const list = (event?.detail?.data || []) as any[]
  list.forEach((item) => {
    if (item && item.type === 'needLogin') {
      console.warn('[webview] H5 提示需要登录')
      toast('H5 提示需要登录')
    }
  })
}
</script>
