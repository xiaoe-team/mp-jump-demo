<template>
  <view class="login-page">
    <view class="login-card">
      <view class="login-brand">{{ brandName }}</view>
      <view class="login-sub">{{ phase === 'loading' ? '正在登录…' : '登录后即可进入直播间' }}</view>

      <view v-if="phase === 'error'" class="login-error">{{ errorMsg || '登录失败，请重试' }}</view>

      <view class="login-agree" @tap="agreed = !agreed">
        <view class="login-check" :class="{ checked: agreed }">
          <text v-if="agreed" class="login-check__mark">✓</text>
        </view>
        <text class="login-agree__text">我已阅读并同意相关服务协议与隐私政策</text>
      </view>

      <t-button
        block
        size="large"
        theme="primary"
        :loading="phase === 'loading'"
        :disabled="phase === 'loading'"
        @click="onLogin"
      >
        {{ phase === 'error' ? '重新登录' : '授权登录' }}
      </t-button>

      <view class="login-later" @tap="goBack">稍后再说</view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { api } from '@/utils/api'
import { XIAOE_APP_ID_TARGET } from '@/config/live'
import { saveSession } from '@/utils/session'
import { globalData } from '@/utils/config'

const brandName = '小鹅通直播演示'
const agreed = ref(false)
const phase = ref<'ready' | 'loading' | 'error'>('ready')
const errorMsg = ref('')
const redirectUri = ref('')

onLoad((query: Record<string, string> = {}) => {
  if (query.redirect_uri) {
    try {
      redirectUri.value = decodeURIComponent(query.redirect_uri)
    } catch {
      redirectUri.value = query.redirect_uri
    }
  }
})

async function onLogin() {
  if (phase.value === 'loading') return
  if (!agreed.value) {
    uni.showToast({ title: '请先阅读并同意协议', icon: 'none' })
    return
  }

  phase.value = 'loading'
  errorMsg.value = ''
  try {
    const login: any = await uni.login()
    if (!login?.code) throw new Error('uni.login 未返回 code')
    const code = login.code
    const res = await api.login(code)
    saveSession({
      token: res.koToken,
      userId: res.userId,
      expiresIn: res.expiresIn,
      appId: XIAOE_APP_ID_TARGET,
    })
    uni.showToast({ title: '登录成功', icon: 'none' })
    finish()
  } catch (error: any) {
    const msg = String(error?.errMsg || error?.message || error)
    const platformLimit = /not supported|uni\.login|wx\.login|不支持/i.test(msg)
    errorMsg.value = msg + (platformLimit ? '（H5 无 wx.login，请在微信小程序里登录）' : '')
    phase.value = 'error'
  }
}

/** 登录完成：优先回到 redirect_uri，否则返回上一页 */
function finish() {
  if (redirectUri.value) {
    uni.redirectTo({
      url: redirectUri.value,
      fail: () => uni.reLaunch({ url: '/pages/index/index' }),
    })
    return
  }
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
    return
  }
  uni.reLaunch({ url: '/pages/index/index' })
}

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
    return
  }
  uni.reLaunch({ url: '/pages/index/index' })
}
</script>

<style>
.login-page {
  min-height: 100vh;
  padding: 80rpx 48rpx;
  box-sizing: border-box;
  background: linear-gradient(180deg, #eaf4ff 0%, #f7fbff 40%, #ffffff 100%);
}

.login-card {
  background: #fff;
  border-radius: 24rpx;
  padding: 56rpx 40rpx 40rpx;
  box-shadow: 0 16rpx 48rpx rgba(20, 114, 255, 0.08);
}

.login-brand {
  font-size: 40rpx;
  font-weight: 700;
  text-align: center;
}

.login-sub {
  margin-top: 16rpx;
  font-size: 26rpx;
  color: #8f959e;
  text-align: center;
}

.login-error {
  margin-top: 28rpx;
  padding: 20rpx;
  border-radius: 12rpx;
  background: #fff1f0;
  color: #d83931;
  font-size: 24rpx;
  line-height: 1.6;
}

.login-agree {
  display: flex;
  align-items: center;
  margin: 48rpx 0 32rpx;
}

.login-check {
  width: 34rpx;
  height: 34rpx;
  margin-right: 14rpx;
  border: 2rpx solid #c9d0d8;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.login-check.checked {
  border-color: #1472ff;
  background: #1472ff;
}

.login-check__mark {
  color: #fff;
  font-size: 22rpx;
  line-height: 1;
}

.login-agree__text {
  font-size: 24rpx;
  color: #5b6570;
}

.login-later {
  margin-top: 32rpx;
  text-align: center;
  font-size: 26rpx;
  color: #8f959e;
}
</style>
