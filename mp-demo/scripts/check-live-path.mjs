// livePath 纯函数断言：node scripts/check-live-path.mjs
// 用 esbuild 把 TS 转成 ESM 后加载，避免为了几个纯函数引入测试框架
import { build } from 'esbuild'
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const result = await build({
  entryPoints: [join(here, '../src/utils/livePath.ts')],
  bundle: true,
  format: 'esm',
  write: false,
  target: 'node18',
})
const mod = await import('data:text/javascript;base64,' + Buffer.from(result.outputFiles[0].text).toString('base64'))
const { buildLivePath, decideKoToken, PAGE_PATH } = mod

let passed = 0
const check = (name, fn) => {
  try {
    fn()
    passed += 1
    console.log('PASS', name)
  } catch (error) {
    console.error('FAIL', name, '\n ', error.message)
    process.exitCode = 1
  }
}

const base = { appId: 'appq6jjgwoo7664', aliveId: 'l_abc' }

check('ko_token 必传：缺 token 抛错', () => {
  assert.throws(() => buildLivePath({ ...base }), /ko_token/)
})

check('带 token 时拼进 path', () => {
  const path = buildLivePath({ ...base, koToken: 'ko-1' })
  assert.equal(path, PAGE_PATH + '?appId=appq6jjgwoo7664&aliveId=l_abc&ko_token=ko-1')
})

check('缺 appId / aliveId 抛错', () => {
  assert.throws(() => buildLivePath({ aliveId: 'l_abc', koToken: 'ko-1' }), /appId/)
  assert.throws(() => buildLivePath({ appId: 'app1', koToken: 'ko-1' }), /aliveId/)
})

check('值会 encodeURIComponent', () => {
  const path = buildLivePath({ appId: 'app 1', aliveId: 'l/a', koToken: 'ko+=1' })
  assert.ok(path.includes('appId=app%201'))
  assert.ok(path.includes('aliveId=l%2Fa'))
  assert.ok(path.includes('ko_token=ko%2B%3D1'))
})

check('share_user_id 可选，空值不拼', () => {
  assert.ok(!buildLivePath({ ...base, koToken: 'ko-1' }).includes('share_user_id'))
  assert.ok(buildLivePath({ ...base, koToken: 'ko-1', shareUserId: 'u_1' }).includes('share_user_id=u_1'))
})

check('decideKoToken：未登录不能跳', () => {
  const d = decideKoToken({ loginStoreAppId: 'a', targetStoreAppId: 'a', koToken: 'ko-1', sessionValid: false })
  assert.equal(d.ok, false)
  assert.match(d.reason, /未登录/)
  assert.equal(d.koToken, '')
})

check('decideKoToken：跨店铺不能跳', () => {
  const d = decideKoToken({ loginStoreAppId: 'a', targetStoreAppId: 'b', koToken: 'ko-1', sessionValid: true })
  assert.equal(d.ok, false)
  assert.match(d.reason, /店铺/)
})

check('decideKoToken：token 过期（空）不能跳', () => {
  const d = decideKoToken({ loginStoreAppId: 'a', targetStoreAppId: 'a', koToken: '', sessionValid: true })
  assert.equal(d.ok, false)
  assert.match(d.reason, /过期/)
})

check('decideKoToken：已登录 + 同店铺 + 有 token 才能跳', () => {
  const d = decideKoToken({ loginStoreAppId: 'a', targetStoreAppId: 'a', koToken: 'ko-1', sessionValid: true })
  assert.equal(d.ok, true)
  assert.equal(d.koToken, 'ko-1')
})

console.log('\n通过 ' + passed + ' / 9 组断言')
