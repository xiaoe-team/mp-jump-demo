<template>
  <view class="page">
    <!-- 顶部：后端与环境 -->
    <view class="card">
      <view class="row-between">
        <text class="title">小鹅通直播跳转演示</text>
        <t-tag theme="primary" size="small" variant="light">{{ envLabel }}</t-tag>
      </view>
      <view class="kv"><text class="k">店铺 app_id</text><text class="v">{{ storeAppId }}</text></view>
      <view class="kv"><text class="k">目标小程序</text><text class="v">{{ targetMiniAppId }}（release）</text></view>
      <view class="tip">跳转参数写在 mp-demo/src/config/live.ts；path 由小程序自己拼，后端不参与。</view>
    </view>

    <!-- 账号 -->
    <view class="card">
      <text class="title">账号</text>
      <view class="kv">
        <text class="k">user_id</text>
        <text class="v" :class="{ warn: !session.valid }">{{ session.userId || '未登录' }}</text>
      </view>
      <view class="kv"><text class="k">ko_token</text><text class="v">{{ tokenTail || '无' }}</text></view>
      <view class="kv"><text class="k">过期时间</text><text class="v">{{ expiresText }}</text></view>
      <view class="kv">
        <text class="k">手机号</text>
        <text class="v" :class="{ warn: session.valid && !bindStatus.isBindPhone }">
          {{ !session.valid ? '未登录' : (bindStatus.isBindPhone ? bindStatus.maskedPhone : '未绑定') }}
        </text>
      </view>
      <view class="kv"><text class="k">跳转携带</text><text class="v" :class="{ warn: !tokenDecision.ok }">{{ tokenDecision.reason }}</text></view>
      <view class="btn-row">
        <t-button size="small" theme="primary" @click="goLogin">{{ session.valid ? '重新登录' : '去登录' }}</t-button>
        <t-button size="small" variant="outline" :disabled="loading || !!jumpingKey" @click="onCheckSession">校验登录态</t-button>
        <t-button size="small" variant="outline" :disabled="loading || !!jumpingKey" @click="onProfile">查用户资料</t-button>
        <t-button v-if="session.valid" size="small" variant="outline" :disabled="loading || !!jumpingKey" @click="onLogout">
          登出
        </t-button>
        <t-button v-if="session.valid && !bindStatus.isBindPhone" size="small" theme="primary" variant="outline" @click="openBindPopup">
          绑定手机号
        </t-button>
        <t-button v-if="session.valid && bindStatus.isBindPhone" size="small" variant="outline" @click="openBindPopup">
          更换/合并手机号
        </t-button>
      </view>
    </view>

    <!-- 两个跳转按钮 -->
    <view class="card">
      <text class="title">进入课程</text>
      <view v-if="missingRooms.length" class="tip warn">未配置 {{ missingRooms.join('、') }} 的 aliveId，请填 mp-demo/src/config/live.ts</view>

      <view v-for="room in rooms" :key="room.key" class="room">
        <view class="row-between">
          <text class="room-title">{{ room.title }}</text>
          <text class="tip">{{ room.desc }}</text>
        </view>
        <view class="path-box">{{ roomPaths[room.key] || '—' }}</view>
        <view class="btn-row">
          <t-button
            size="medium"
            theme="primary"
            :loading="jumpingKey === room.key"
            :disabled="!room.ready || (!!jumpingKey && jumpingKey !== room.key)"
            @click="onJump(room)"
          >
            {{ room.ready ? '跳转' : '未配置 aliveId' }}
          </t-button>
          <t-button size="medium" variant="outline" :disabled="!room.ready" @click="onCopyPath(room)">复制 path</t-button>
        </view>
      </view>
    </view>

    <!-- 内嵌 H5 演示 -->
    <view class="card">
      <text class="title">内嵌 H5</text>
      <view class="tip">演示 web-view 用法：域名白名单、内嵌标识参数、H5 登录态交接。</view>
      <view class="btn-row">
        <t-button size="small" variant="outline" @click="onOpenWebView">打开内嵌 H5</t-button>
      </view>
    </view>

    <!-- 日志 -->
    <view class="card">
      <view class="row-between">
        <text class="title">日志</text>
        <text class="link" @tap="logs = []">清空</text>
      </view>
      <view v-if="!logs.length" class="tip">还没有操作记录</view>
      <view v-for="(item, index) in logs" :key="index" class="log">{{ item }}</view>
    </view>

    <bind-phone-popup
      v-model:visible="showBindPopup"
      :token="session.token"
      @bound="onPhoneBound"
      @need-login="onBindNeedLogin"
    />
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { api } from '@/utils/api'
import { buildLivePath, decideKoToken } from '@/utils/livePath'
import { LIVE_MP_WX_APP_ID, ROOMS, XIAOE_APP_ID_TARGET, type RoomConfig } from '@/config/live'
import {
  clearSession,
  formatExpiresAt,
  getFreshKoToken,
  getSession,
  saveSession,
  saveWxUserProfile,
  type Session,
} from '@/utils/session'
import BindPhonePopup from '@/components/bind-phone-popup/index.vue'
import { buildCourseH5Url, buildH5Url, globalData } from '@/utils/config'

// 全局忙碌态：校验登录态 / 查资料 / 登出这类与房间无关的动作
const loading = ref(false)
// 跳转忙碌态：记录「哪个房间正在跳」，避免两个跳转按钮互相带着转圈
const jumpingKey = ref('')
const logs = ref<string[]>([])
const session = ref<Session>({ token: '', userId: '', expiresAt: 0, valid: false })

// 跳转参数全部来自前端写死的配置
const storeAppId = XIAOE_APP_ID_TARGET
const targetMiniAppId = LIVE_MP_WX_APP_ID
const envLabel = globalData.ENV + ' · release'

// 手机号绑定状态与弹窗
const bindStatus = ref<{ isBindPhone: boolean; maskedPhone: string }>({ isBindPhone: false, maskedPhone: '' })
const showBindPopup = ref(false)
/** 因未绑定手机号被打断的跳转，绑定成功后接着跳 */
const pendingRoom = ref<RoomConfig | null>(null)
/** 从登录页回来后要自动进入的房间 key */
let pendingAutoJump = ''

const rooms: Array<RoomConfig & { ready: boolean }> = ROOMS.map((room) => ({
  ...room,
  ready: Boolean(String(room.aliveId || '').trim()),
}))
const missingRooms = rooms.filter((room) => !room.ready).map((room) => room.title)

const tokenTail = computed(() => {
  const token = session.value.token
  if (!token) return ''
  const fresh = getFreshKoToken()
  const shown = token.length > 10 ? token.slice(0, 8) + '…' + token.slice(-4) : token
  return fresh ? shown : shown + '（已过期）'
})
const expiresText = computed(() => formatExpiresAt(session.value.expiresAt))

/** 这次跳转能否进行（ko_token 必传；未登录 / 跨店铺 / 过期都拦） */
const tokenDecision = computed(() =>
  decideKoToken({
    loginStoreAppId: storeAppId,
    targetStoreAppId: storeAppId,
    koToken: getFreshKoToken(),
    sessionValid: session.value.valid,
  }),
)

/** 每个房间将要使用的 path —— 完全在前端拼装 */
const roomPaths = computed(() => {
  const map: Record<string, string> = {}
  for (const room of rooms) {
    if (!room.ready) {
      map[room.key] = '未配置 aliveId'
      continue
    }
    if (!tokenDecision.value.ok) {
      map[room.key] = '需先登录（ko_token 必传）'
      continue
    }
    try {
      map[room.key] = buildLivePath({
        appId: storeAppId,
        aliveId: room.aliveId,
        koToken: tokenDecision.value.koToken,
      })
    } catch (error: any) {
      map[room.key] = '拼装失败：' + error.message
    }
  }
  return map
})

function log(text: string) {
  const ts = new Date()
  const pad = (n: number) => (n < 10 ? '0' + n : String(n))
  const stamp = pad(ts.getHours()) + ':' + pad(ts.getMinutes()) + ':' + pad(ts.getSeconds())
  logs.value = [stamp + '  ' + text, ...logs.value].slice(0, 30)
}

function refreshSession() {
  session.value = getSession()
}

/** 静默刷新手机号绑定状态（不弹窗；弹窗只在点「跳转」时触发） */
async function refreshBindStatus() {
  if (!session.value.valid) {
    bindStatus.value = { isBindPhone: false, maskedPhone: '' }
    return
  }
  try {
    const res = await api.checkBindPhone(session.value.token)
    bindStatus.value = { isBindPhone: Boolean(res.isBindPhone), maskedPhone: res.maskedPhone || '' }
  } catch (error: any) {
    log('查询手机号绑定状态失败：' + (error?.message || error))
  }
}

function openBindPopup() {
  const token = getFreshKoToken() || session.value.token
  log('打开绑定弹窗，登录态=' + (token ? '有（' + token.slice(-4) + '）' : '无'))
  showBindPopup.value = true
}

/** 弹窗发现登录态失效：收起弹窗并去登录 */
function onBindNeedLogin() {
  showBindPopup.value = false
  pendingRoom.value = null
  log('手机号授权前登录态已失效，去登录页')
  goLogin()
}

async function onPhoneBound(payload: { maskedPhone: string; merged: boolean }) {
  bindStatus.value = { isBindPhone: true, maskedPhone: payload.maskedPhone }
  log((payload.merged ? '账号已合并：' : '手机号绑定成功：') + payload.maskedPhone)

  const room = pendingRoom.value
  pendingRoom.value = null
  if (room) {
    log('手机号已绑定，继续「' + room.title + '」')
    await onJump(room)
  }
}

onLoad((query: Record<string, string> = {}) => {
  refreshSession()
  refreshBindStatus()
  pendingAutoJump = query.autoJump || ''
  log('跳转参数来自 mp-demo/src/config/live.ts，未配置：' + (missingRooms.length ? missingRooms.join('、') : '无'))
})

onShow(async () => {
  refreshSession()
  await refreshBindStatus()

  if (!pendingAutoJump) return
  const key = pendingAutoJump
  pendingAutoJump = ''
  if (!session.value.valid) return

  const room = rooms.find((item) => item.key === key)
  if (!room) return
  log('登录完成，自动继续进入「' + room.title + '」')
  await onJump(room)
})

/** 跳到专门的登录页；roomKey 有值时登录成功后会回到首页并继续进入该直播间 */
function goLogin(roomKey?: string) {
  const redirect = roomKey ? '/pages/index/index?autoJump=' + roomKey : '/pages/index/index'
  log('跳转登录页，redirect=' + redirect)
  uni.navigateTo({ url: '/pages/login/index?redirect_uri=' + encodeURIComponent(redirect) })
}

async function onCheckSession() {
  if (loading.value || jumpingKey.value) return
  loading.value = true
  try {
    const token = getFreshKoToken() || session.value.token
    const res = await api.checkSession(token)
    log('check_login → valid=' + res.valid + (res.userId ? ' user_id=' + res.userId : '') + (res.msg ? ' msg=' + res.msg : ''))
    if (!res.valid) {
      clearSession()
      refreshSession()
    }
  } catch (error: any) {
    log('校验失败：' + error.message)
  } finally {
    loading.value = false
  }
}

async function onProfile() {
  if (loading.value || jumpingKey.value) return
  loading.value = true
  try {
    const res = await api.profile(getFreshKoToken() || session.value.token)
    saveWxUserProfile({ nickname: res.nickname, avatar: res.avatar })
    log(
      '用户资料 → user_id=' + (res.userId || '-') +
        ' 手机号已绑定=' + res.isBindPhone + ' ' + (res.maskedPhone || '') +
        (res.nickname ? ' 昵称=' + res.nickname : ''),
    )
  } catch (error: any) {
    log('查资料失败：' + error.message)
  } finally {
    loading.value = false
  }
}

function onLogout() {
  clearSession()
  refreshSession()
  bindStatus.value = { isBindPhone: false, maskedPhone: '' }
  pendingRoom.value = null
  log('已登出（本地登录态已清空）')
}

/** 点「跳转」：校验登录态与手机号绑定，然后调起鹅直播小程序 */
async function onJump(room: RoomConfig) {
  if (jumpingKey.value) return
  if (!room.ready) {
    uni.showToast({ title: '未配置该房间 aliveId', icon: 'none' })
    return
  }
  if (!session.value.valid) {
    log('未登录，拦截「' + room.title + '」并跳登录')
    goLogin(room.key)
    return
  }
  if (!getFreshKoToken()) {
    log('本地 ko_token 已过期，请重新登录')
    goLogin()
    return
  }

  jumpingKey.value = room.key
  try {
    // 手机号未绑定：弹窗拦截，绑定成功后回到本函数继续跳
    const status = await api.checkBindPhone(session.value.token)
    bindStatus.value = { isBindPhone: Boolean(status.isBindPhone), maskedPhone: status.maskedPhone || '' }
    if (!bindStatus.value.isBindPhone) {
      pendingRoom.value = room
      showBindPopup.value = true
      log('手机号未绑定，拦截「' + room.title + '」')
      return
    }

    const path = roomPaths.value[room.key]
    if (!path) {
      log('path 不可用：' + path)
      return
    }
    if (typeof uni.navigateToMiniProgram !== 'function') {
      log('当前平台没有 navigateToMiniProgram，请在微信小程序里试')
      return
    }
    log('跳转 ' + room.title + '：' + path)
    uni.navigateToMiniProgram({
      appId: targetMiniAppId,
      path,
      envVersion: 'release', // 鹅直播只接受正式版跳转，写死不可配置
      success: () => log('跳转成功：' + room.title),
      fail: (err) => log('跳转失败：' + ((err && err.errMsg) || String(err))),
    })
  } catch (error: any) {
    log('跳转前校验失败：' + (error?.message || error))
  } finally {
    jumpingKey.value = ''
  }
}

function onOpenWebView() {
  // 优先打开课程详情 H5（/p/course/ecourse/{courseId}）；没配课程 ID 时退回域名首页
  const courseUrl = buildCourseH5Url()
  const url = courseUrl || buildH5Url()
  if (!url) {
    log('没有可用的 H5 地址：请配置 VITE_H5_BASE（课程页还需 VITE_H5_COURSE_ID）')
    return
  }
  log(courseUrl ? '打开课程 H5：' + courseUrl : '未配置 VITE_H5_COURSE_ID，打开域名首页：' + url)
  uni.navigateTo({ url: '/pages/webview/index?url=' + encodeURIComponent(url) })
}

function onCopyPath(room: { key: string; title: string }) {
  const path = roomPaths.value[room.key]
  if (!path) return
  uni.setClipboardData({
    data: path,
    success: () => log('已复制 ' + room.title + ' 的 path'),
  })
}
</script>

<style>
.page {
  padding: 24rpx 24rpx 60rpx;
  box-sizing: border-box;
}

.card {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
}

.title {
  display: block;
  font-size: 30rpx;
  font-weight: 600;
  margin-bottom: 16rpx;
}

.row-between {
  display: flex;
  align-items: center;
  justify-content: space-between;
}


.kv {
  display: flex;
  margin-bottom: 10rpx;
  font-size: 26rpx;
}

.kv .k {
  width: 190rpx;
  color: #8f959e;
  flex-shrink: 0;
}

.kv .v {
  flex: 1;
  word-break: break-all;
}

.warn {
  color: #d83931;
}

.tip {
  font-size: 24rpx;
  color: #8f959e;
  line-height: 1.6;
  margin-top: 8rpx;
}

.btn-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
  margin-top: 16rpx;
  align-items: center;
}

.btn {
  margin: 0;
  font-size: 26rpx;
  line-height: 2.2;
  padding: 0 24rpx;
  border-radius: 10rpx;
  background: #f2f3f5;
  color: #1f2329;
}

.btn.primary {
  background: #1472ff;
  color: #fff;
}

.btn.jump {
  height: 80rpx;
  line-height: 80rpx;
  font-size: 28rpx;
  font-weight: 600;
  background: #1472ff;
  color: #fff;
  border-radius: 12rpx;
}

.btn.jump.disabled {
  background: #c9d4e5;
}

.room {
  margin-top: 20rpx;
  padding-top: 20rpx;
  border-top: 1rpx solid #f0f1f3;
}

.room-title {
  font-size: 28rpx;
  font-weight: 600;
}

.path-box {
  margin-top: 12rpx;
  background: #1f2329;
  color: #9fe3a0;
  border-radius: 12rpx;
  padding: 18rpx;
  font-family: Menlo, monospace;
  font-size: 22rpx;
  line-height: 1.6;
  word-break: break-all;
}

.log {
  font-size: 22rpx;
  color: #6b7280;
  font-family: Menlo, monospace;
  line-height: 1.7;
  word-break: break-all;
}

.link {
  font-size: 24rpx;
  color: #1472ff;
}
</style>
