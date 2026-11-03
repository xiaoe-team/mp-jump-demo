<template>
  <t-popup v-model:visible="visibleProxy" placement="bottom" @visible-change="onVisibleChange">
    <view class="bind-phone">
      <view class="bind-phone__title">{{ merging ? '确认合并账号' : '绑定手机号' }}</view>

      <template v-if="!merging">
        <view class="bind-phone__desc">为了给您更好地直播体验，请授权手机号</view>
        <button
          class="bind-phone__auth"
          open-type="getPhoneNumber"
          :loading="loading"
          :disabled="loading"
          @getphonenumber="onGetPhoneNumber"
        >
          {{ loading ? '授权中…' : '授权手机号' }}
        </button>
      </template>

      <template v-else>
        <view class="bind-phone__desc">
          手机号 {{ maskedPhone }} 已绑定其他账号。确认后两个账号的权益（已购内容、会员等）会一起合并到该手机号账号下，
          原账号不再单独登录，合并不可撤销。
        </view>
        <view class="bind-phone__actions">
          <t-button size="medium" variant="outline" :disabled="loading" @click="onCancel">取消</t-button>
          <t-button size="medium" theme="primary" :loading="loading" @click="onConfirmMerge">确认合并</t-button>
        </view>
      </template>

      <view v-if="errorText" class="bind-phone__error">{{ errorText }}</view>

      <view class="bind-phone__later" @tap="onCancel">稍后再说</view>
    </view>
  </t-popup>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api } from '@/utils/api'
import { getFreshKoToken, getSession } from '@/utils/session'

const props = defineProps<{
  visible: boolean
  token: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'bound', payload: { maskedPhone: string; merged: boolean }): void
  (e: 'need-login'): void
}>()

const loading = ref(false)
const errorText = ref('')
const merging = ref(false)
const bindToken = ref('')
const maskedPhone = ref('')

const visibleProxy = computed({
  get: () => props.visible,
  set: (value: boolean) => emit('update:visible', value),
})

watch(
  () => props.visible,
  (open) => {
    if (open) {
      // 每次重新打开都回到第一步
      merging.value = false
      bindToken.value = ''
      maskedPhone.value = ''
      errorText.value = ''
    }
  },
)

function onVisibleChange(event: any) {
  emit('update:visible', Boolean(event?.detail?.visible))
}

function onCancel() {
  merging.value = false
  emit('update:visible', false)
}

/** 当前登录态：优先用传入的，其次读本地存储（防止父组件状态滞后） */
function currentToken(): string {
  return props.token || getFreshKoToken() || getSession().token
}

/** 微信手机号授权：阶段一（code 换手机号 + 冲突检测） */
async function onGetPhoneNumber(event: any) {
  const code = event?.detail?.code
  if (!code) {
    errorText.value = '未授权手机号，可稍后再说'
    return
  }
  const token = currentToken()
  if (!token) {
    errorText.value = '登录态已失效，请重新登录'
    emit('need-login')
    return
  }

  loading.value = true
  errorText.value = ''
  try {
    const res = await api.bindOrMergePhone({ token, code })
    if (res.needMergeConfirm && res.bindToken) {
      merging.value = true
      bindToken.value = res.bindToken
      maskedPhone.value = res.maskedPhone || ''
      return
    }
    finish(res.maskedPhone || '')
  } catch (error: any) {
    errorText.value = error?.message || '手机号绑定失败'
  } finally {
    loading.value = false
  }
}

/** 阶段二：用户确认合并 */
async function onConfirmMerge() {
  if (!bindToken.value) {
    errorText.value = '确认凭证已失效，请重新授权手机号'
    merging.value = false
    return
  }

  const token = currentToken()
  if (!token) {
    errorText.value = '登录态已失效，请重新登录'
    emit('need-login')
    return
  }

  loading.value = true
  errorText.value = ''
  try {
    const res = await api.bindOrMergePhone({
      token,
      bind_token: bindToken.value,
      confirm_merge: true,
    })
    finish(res.maskedPhone || maskedPhone.value, true)
  } catch (error: any) {
    errorText.value = error?.message || '账号合并失败'
  } finally {
    loading.value = false
  }
}

function finish(phone: string, merged = false) {
  merging.value = false
  bindToken.value = ''
  emit('update:visible', false)
  uni.showToast({ title: merged ? '账号已合并' : '手机号绑定成功', icon: 'none' })
  emit('bound', { maskedPhone: phone, merged })
}
</script>

<style>
.bind-phone {
  padding: 40rpx 40rpx 60rpx;
  background: #fff;
}

.bind-phone__title {
  font-size: 34rpx;
  font-weight: 600;
  text-align: center;
  margin-bottom: 24rpx;
}

.bind-phone__desc {
  font-size: 26rpx;
  color: #8f959e;
  line-height: 1.7;
  margin-bottom: 32rpx;
}

.bind-phone__auth {
  width: 100%;
  height: 88rpx;
  line-height: 88rpx;
  border-radius: 12rpx;
  background: #1472ff;
  color: #fff;
  font-size: 30rpx;
  font-weight: 600;
}

.bind-phone__actions {
  display: flex;
  gap: 20rpx;
}

.bind-phone__error {
  margin-top: 20rpx;
  font-size: 24rpx;
  color: #d83931;
}

.bind-phone__later {
  margin-top: 28rpx;
  text-align: center;
  font-size: 26rpx;
  color: #8f959e;
}
</style>
