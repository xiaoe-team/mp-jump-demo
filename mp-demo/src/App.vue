<script lang="ts">
import { globalData } from '@/utils/config'

// 把全局配置挂到 getApp().globalData（小程序端可用；H5 端没有 getApp，直接 import globalData）
export default {
  globalData: {
    ...globalData,
  },
}
</script>

<script setup lang="ts">
import { onLaunch } from '@dcloudio/uni-app'
import { api } from '@/utils/api'
import { clearExpiredSession, getSession } from '@/utils/session'

onLaunch(async () => {
  // 冷启动先清掉明确过期的登录态，避免用过期凭证发请求
  const cleared = clearExpiredSession()

  // 静默校验登录态：有 token 才校验，失败不打扰用户，交给页面自己提示
  const session = getSession()
  if (session.valid) {
    try {
      const result = await api.checkSession(session.token)
      if (!result.valid) {
        clearExpiredSession()
        console.log('[jump-xiaoe-live-demo] 登录态已失效', result.msg || '')
      }
    } catch (error: any) {
      console.warn('[jump-xiaoe-live-demo] 冷启动校验失败', error && error.message)
    }
  }

  console.log('[jump-xiaoe-live-demo] app launched', { env: globalData.ENV, clearedExpired: cleared })
})
</script>

<style>
page {
  background: #f5f6f8;
  color: #1f2329;
  font-family: -apple-system, 'PingFang SC', 'Helvetica Neue', sans-serif;
}
</style>
