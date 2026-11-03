"""后端接口测试（上游用 stub transport，不发真实网络请求）。"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services import login_service as login_service_module  # noqa: E402
from app.services.login_service import build_wechat_client, build_xiaoe_client  # noqa: E402


class FakeUpstream:
    """记录调用并返回预设响应的小鹅云/微信假上游。"""

    def __init__(self):
        self.calls = []
        self.access_token_calls = 0
        self.fail_registers_with_2008 = 0
        self.missing_union_id = False
        self.invalid_ko_token = False
        self.phone = "13812341234"
        self.bind_calls = []
        self.phone_owner_user_id = ""  # 该手机号已属于别的账号时填 user_id
        self.wechat_phone = "13812341234"
        self.wechat_phone_watermark = "wx_test"

    def xiaoe(self, url: str, method: str, headers: Dict[str, str], body, timeout: float) -> Tuple[int, str]:
        self.calls.append(("xiaoe", method, url, headers, body))
        if "/token?" in url or url.endswith("/token"):
            self.access_token_calls += 1
            return 200, json.dumps({"code": 0, "data": {"access_token": "at-%d" % self.access_token_calls, "expires_in": 7200}})
        if "/xe.user.register/" in url:
            if self.fail_registers_with_2008 > 0:
                self.fail_registers_with_2008 -= 1
                return 200, json.dumps({"code": 2008, "msg": "token expired"})
            return 200, json.dumps({"code": 0, "data": {"app_id": "app_test", "user_id": "u_1", "user_exists": 2}})
        if "/xe.sdk.account.login/" in url:
            return 200, json.dumps(
                {"code": 0, "data": {"token_key": "ko_token", "token_value": "ko-abc", "user_id": "u_1", "sdk_user_id": "un_1", "expires": 7200}}
            )
        if "/xe.user.info.get/" in url:
            payload = json.loads(body.decode("utf-8")) if body else {}
            data_block = payload.get("data") or {}
            has_identity = bool(payload.get("user_id") or data_block.get("wx_union_id") or data_block.get("phone"))
            if not has_identity:
                return 200, json.dumps({"code": -1, "msg": "user_id,wx_union_id,wx_open_id,phone must have one"})
            if data_block.get("phone"):
                if self.phone_owner_user_id:
                    return 200, json.dumps({"code": 0, "data": {"user_id": self.phone_owner_user_id}})
                return 200, json.dumps({"code": -1, "msg": "user not found"})
            if self.invalid_ko_token:
                return 200, json.dumps({"code": 40004, "msg": "登录态不存在或已过期"})
            return 200, json.dumps(
                {"code": 0, "data": {"user_id": "u_1", "nickname": "小明", "avatar": "https://a/b.png", "phone": self.phone}}
            )
        if "/xe.account-platform.uaccount.bind_or_merge_phone/" in url:
            payload = json.loads(body.decode("utf-8")) if body else {}
            self.bind_calls.append(payload)
            return 200, json.dumps({"code": 0, "data": {"bind_result": {"can_bind": True, "need_bind": True}}})
        if "/xe.login.url/" in url:
            return 200, json.dumps({"code": 0, "data": {"login_url": "https://h5.example.com/sso?t=1"}})
        raise AssertionError("未预期的上游调用：" + url)

    def wechat(self, url: str, method: str, headers: Dict[str, str], body, timeout: float) -> Tuple[int, str]:
        self.calls.append(("wechat", method, url, headers, body))
        if "/cgi-bin/stable_token" in url:
            return 200, json.dumps({"access_token": "wx-at-1", "expires_in": 7200})
        if "/wxa/business/getuserphonenumber" in url:
            return 200, json.dumps(
                {"errcode": 0, "phone_info": {"purePhoneNumber": self.wechat_phone, "watermark": {"appid": self.wechat_phone_watermark}}}
            )
        if "/sns/jscode2session" in url:
            if "js_code=bad" in url:
                return 200, json.dumps({"errcode": 40029, "errmsg": "invalid code"})
            if self.missing_union_id:
                return 200, json.dumps({"openid": "openid_1", "session_key": "sk"})
            return 200, json.dumps({"openid": "openid_1", "unionid": "un_1", "session_key": "sk"})
        raise AssertionError("未预期的微信调用：" + url)

    def body_of(self, keyword: str):
        for _kind, _method, url, _headers, body in reversed(self.calls):
            if keyword in url:
                return json.loads(body.decode("utf-8")) if body else {}
        raise AssertionError("没有调用：" + keyword)


def build_settings(**overrides) -> Settings:
    base = dict(
        port=8090,
        api_base_url="https://api.xiaoe-tech.com",
        store_app_id="app_test",
        client_id="cid",
        client_secret="csecret",
        sdk_app_id="sdkapp",
        sdk_secret="sdksecret",
        wechat_api_base_url="https://api.weixin.qq.com",
        wx_app_id="wx_test",
        wx_app_secret="wxsecret",
        env_name="test",
        config_files=["(env only)"],
        request_timeout_ms=5000,
        openapi_server_url="https://example.test",
    )
    base.update(overrides)
    return Settings(**base)


class ApiTestBase(unittest.TestCase):
    settings_overrides: Dict = {}

    def setUp(self) -> None:
        self.upstream = FakeUpstream()
        settings = build_settings(**self.settings_overrides)
        original_x, original_w = build_xiaoe_client, build_wechat_client
        login_service_module.build_xiaoe_client = lambda config, transport=None: original_x(config, self.upstream.xiaoe)
        login_service_module.build_wechat_client = lambda config, transport=None: original_w(config, self.upstream.wechat)
        self.addCleanup(lambda: setattr(login_service_module, "build_xiaoe_client", original_x))
        self.addCleanup(lambda: setattr(login_service_module, "build_wechat_client", original_w))
        self.client = TestClient(create_app(settings))

    def envelope(self, response):
        self.assertEqual(response.status_code, 200)
        body = response.json()
        for key in ("code", "msg", "data", "trace_id"):
            self.assertIn(key, body)
        self.assertTrue(body["trace_id"])
        self.assertEqual(response.headers.get("X-Trace-ID"), body["trace_id"])
        return body


class LoginFlowTest(ApiTestBase):
    def test_login_success_chain(self):
        body = self.envelope(self.client.post("/api/login", json={"wx_app_id": "wx_test", "code": "good"}))
        self.assertEqual(body["code"], 0)
        self.assertEqual(body["data"]["koToken"], "ko-abc")
        self.assertEqual(body["data"]["userId"], "u_1")
        self.assertEqual(body["data"]["expiresIn"], 7200)

        kinds = [call[0] for call in self.upstream.calls]
        urls = [call[2] for call in self.upstream.calls]
        self.assertEqual(kinds[0], "wechat")
        self.assertIn("/token?", urls[1])
        self.assertIn("/xe.user.register/1.0.0", urls[2])
        self.assertIn("/xe.sdk.account.login/1.0.0", urls[3])

        register = self.upstream.body_of("/xe.user.register/")
        self.assertEqual(register["data"]["wx_union_id"], "un_1")
        self.assertEqual(register["data"]["sdk_user_id"], "un_1")
        self.assertEqual(register["data"]["sdk_app_id"], "sdkapp")

        sdk_login = self.upstream.body_of("/xe.sdk.account.login/")
        self.assertEqual(sdk_login["app_user_id"], "un_1")
        self.assertEqual(sdk_login["user_info"]["union_id"], "un_1")
        self.assertEqual(sdk_login["sdk_app_id"], "sdkapp")

    def test_login_rejects_wx_app_id_mismatch(self):
        body = self.envelope(self.client.post("/api/login", json={"wx_app_id": "wx_other", "code": "good"}))
        self.assertEqual(body["code"], -1)
        self.assertIn("wx_app_id", body["msg"])

    def test_login_requires_code(self):
        body = self.envelope(self.client.post("/api/login", json={"wx_app_id": "wx_test"}))
        self.assertEqual(body["code"], -1)
        self.assertIn("code", body["msg"])

    def test_wechat_invalid_code_is_surfaced(self):
        body = self.envelope(self.client.post("/api/login", json={"wx_app_id": "wx_test", "code": "bad"}))
        self.assertEqual(body["code"], -1)
        self.assertIn("40029", body["msg"])

    def test_missing_union_id_is_error(self):
        self.upstream.missing_union_id = True
        body = self.envelope(self.client.post("/api/login", json={"wx_app_id": "wx_test", "code": "good"}))
        self.assertEqual(body["code"], -1)
        self.assertIn("union_id", body["msg"])

    def test_access_token_expired_retries_once(self):
        self.upstream.fail_registers_with_2008 = 1
        body = self.envelope(self.client.post("/api/login", json={"wx_app_id": "wx_test", "code": "good"}))
        self.assertEqual(body["code"], 0)
        self.assertEqual(self.upstream.access_token_calls, 2)


class SessionTest(ApiTestBase):
    def _login(self):
        body = self.envelope(self.client.post("/api/login", json={"wx_app_id": "wx_test", "code": "good"}))
        self.assertEqual(body["code"], 0)
        return body["data"]["koToken"]

    def test_check_login_after_login(self):
        ko = self._login()
        body = self.envelope(self.client.post("/api/session/check", json={"token": ko}))
        self.assertEqual(body["code"], 0)
        self.assertTrue(body["data"]["valid"])
        self.assertEqual(body["data"]["userId"], "u_1")

    def test_check_login_unknown_token(self):
        body = self.envelope(self.client.post("/api/session/check", json={"token": "ko-never-issued"}))
        self.assertEqual(body["code"], 0)
        self.assertFalse(body["data"]["valid"])
        self.assertIn("过期", body["data"]["msg"])

    def test_check_login_without_token(self):
        body = self.envelope(self.client.post("/api/session/check", json={}))
        self.assertFalse(body["data"]["valid"])
        self.assertIn("ko_token", body["data"]["msg"])

    def test_profile_requires_login(self):
        body = self.envelope(self.client.post("/api/profile", json={"token": "ko-never-issued"}))
        self.assertEqual(body["code"], -1)
        self.assertIn("过期", body["msg"])

    def test_profile_masks_phone(self):
        ko = self._login()
        body = self.envelope(self.client.post("/api/profile", json={"token": ko}))
        self.assertEqual(body["code"], 0)
        self.assertTrue(body["data"]["isBindPhone"])
        self.assertEqual(body["data"]["maskedPhone"], "138****1234")
        # 查资料时带上 user_id（上游要求四种身份之一）
        info_call = [c for c in self.upstream.calls if "/xe.user.info.get/" in c[2]][-1]
        self.assertEqual(json.loads(info_call[4].decode("utf-8"))["user_id"], "u_1")

    def test_login_url(self):
        body = self.envelope(
            self.client.post(
                "/api/login-url",
                json={"wx_app_id": "wx_test", "code": "good", "redirect_uri": "https://xiaoe.david-tech.cn/x"},
            )
        )
        self.assertEqual(body["code"], 0)
        self.assertTrue(body["data"]["loginUrl"].startswith("https://h5.example.com/sso"))
        payload = self.upstream.body_of("/xe.login.url/")   # body_of 已解析成 dict
        self.assertIn("redirect_uri", json.dumps(payload))
        # login_type 必须是 4：1/2/5 换回 PC 登录页、3 换回平台 H5 登录页，
        # 只有 4 会把 redirect_uri 换回业务页并带 state，web-view 内嵌才进得去
        self.assertEqual(payload["data"]["login_type"], 4)

    def test_login_url_redirect_uri_drops_platform_params(self):
        """app_env_type / app_id 不能带给上游：平台换地址时会自己补，传过去就重复了；
        其它业务参数（如 type=2）必须原样保留。"""
        body = self.envelope(
            self.client.post(
                "/api/login-url",
                json={
                    "wx_app_id": "wx_test",
                    "code": "good",
                    "redirect_uri": "https://xiaoe.david-tech.cn/p/course/ecourse/preview/c1"
                    "?app_env_type=mini_program_wechat_sdk&app_id=appq6jjgwoo7664&type=2",
                },
            )
        )
        self.assertEqual(body["code"], 0)
        sent = self.upstream.body_of("/xe.login.url/")["data"]["redirect_uri"]
        self.assertNotIn("app_env_type", sent)
        self.assertNotIn("app_id=", sent)
        self.assertIn("type=2", sent)
        self.assertIn("/p/course/ecourse/preview/c1", sent)


class PhoneBindTest(ApiTestBase):
    def _login(self) -> str:
        body = self.envelope(self.client.post("/api/login", json={"wx_app_id": "wx_test", "code": "good"}))
        return body["data"]["koToken"]

    def test_check_bind_phone_not_bound(self):
        ko = self._login()
        body = self.envelope(self.client.post("/api/check-bind-phone", json={"token": ko}))
        self.assertEqual(body["code"], 0)
        self.assertTrue(body["data"]["isBindPhone"])
        self.assertEqual(body["data"]["maskedPhone"], "138****1234")

    def test_check_bind_phone_requires_login(self):
        body = self.envelope(self.client.post("/api/check-bind-phone", json={"token": "ko-never"}))
        self.assertEqual(body["code"], -1)
        self.assertIn("过期", body["msg"])

    def test_bind_without_conflict_binds_directly(self):
        ko = self._login()
        body = self.envelope(self.client.post("/api/bind-or-merge-phone", json={"token": ko, "code": "phone-code"}))
        self.assertEqual(body["code"], 0)
        self.assertTrue(body["data"]["success"])
        self.assertFalse(body["data"]["needMergeConfirm"])
        self.assertEqual(self.upstream.bind_calls[-1]["phone"], "13812341234")

    def test_bind_conflict_returns_need_merge_confirm(self):
        self.upstream.phone_owner_user_id = "u_other"
        ko = self._login()
        body = self.envelope(self.client.post("/api/bind-or-merge-phone", json={"token": ko, "code": "phone-code"}))
        self.assertEqual(body["code"], 0)
        self.assertFalse(body["data"]["success"])
        self.assertTrue(body["data"]["needMergeConfirm"])
        self.assertTrue(body["data"]["bindToken"])
        self.assertEqual(body["data"]["conflictUserId"], "u_other")
        self.assertEqual(body["data"]["maskedPhone"], "138****1234")
        # 冲突阶段不应调用绑定接口
        self.assertEqual(len(self.upstream.bind_calls), 0)

    def test_confirm_merge_uses_bind_token(self):
        self.upstream.phone_owner_user_id = "u_other"
        ko = self._login()
        first = self.envelope(self.client.post("/api/bind-or-merge-phone", json={"token": ko, "code": "phone-code"}))
        bind_token = first["data"]["bindToken"]

        second = self.envelope(
            self.client.post(
                "/api/bind-or-merge-phone",
                json={"token": ko, "bind_token": bind_token, "confirm_merge": True},
            )
        )
        self.assertEqual(second["code"], 0)
        self.assertTrue(second["data"]["success"])
        self.assertTrue(second["data"]["merged"])
        self.assertEqual(self.upstream.bind_calls[-1]["phone"], "13812341234")

    def test_confirm_merge_requires_explicit_flag(self):
        self.upstream.phone_owner_user_id = "u_other"
        ko = self._login()
        bind_token = self.envelope(
            self.client.post("/api/bind-or-merge-phone", json={"token": ko, "code": "phone-code"})
        )["data"]["bindToken"]

        body = self.envelope(
            self.client.post("/api/bind-or-merge-phone", json={"token": ko, "bind_token": bind_token})
        )
        self.assertEqual(body["code"], -1)
        self.assertIn("confirm_merge", body["msg"])

    def test_bind_token_is_one_time(self):
        self.upstream.phone_owner_user_id = "u_other"
        ko = self._login()
        bind_token = self.envelope(
            self.client.post("/api/bind-or-merge-phone", json={"token": ko, "code": "phone-code"})
        )["data"]["bindToken"]

        payload = {"token": ko, "bind_token": bind_token, "confirm_merge": True}
        self.envelope(self.client.post("/api/bind-or-merge-phone", json=payload))
        again = self.envelope(self.client.post("/api/bind-or-merge-phone", json=payload))
        self.assertEqual(again["code"], -1)
        self.assertIn("失效", again["msg"])

    def test_phone_watermark_mismatch_rejected(self):
        self.upstream.wechat_phone_watermark = "wx_other"
        ko = self._login()
        body = self.envelope(self.client.post("/api/bind-or-merge-phone", json={"token": ko, "code": "phone-code"}))
        self.assertEqual(body["code"], -1)
        self.assertIn("不匹配", body["msg"])


class UpstreamEndpointTest(unittest.TestCase):
    """把「用到的上游接口」钉死，避免悄悄多调或漏调。"""

    def test_xiaoe_endpoints_are_documented(self):
        from app.services.client_service import xiaoe_client

        self.assertEqual(
            {name: method for name, (method, _path) in xiaoe_client.ENDPOINTS.items()},
            {
                "token": "GET",
                "register": "POST",
                "sdkLogin": "POST",
                "userInfo": "POST",
                "bindOrMergePhone": "POST",
                "loginUrl": "POST",
            },
        )
        self.assertEqual(len({path for _m, path in xiaoe_client.ENDPOINTS.values()}), 6)

    def test_wechat_endpoints_are_documented(self):
        from app.services.client_service import wechat_client

        self.assertEqual(
            {name: method for name, (method, _path) in wechat_client.ENDPOINTS.items()},
            {"jscode2session": "GET", "stableToken": "POST", "getPhoneNumber": "POST"},
        )

    def test_full_login_flow_only_touches_documented_xiaoe_endpoints(self):
        """跑一遍登录 + 绑定手机号，实际调到的上游路径必须是清单里的子集。"""
        from app.services.client_service import xiaoe_client, wechat_client

        upstream = FakeUpstream()
        settings = build_settings()
        svc = login_service_module.LoginService(
            settings,
            xiaoe=build_xiaoe_client(settings, upstream.xiaoe),
            wechat=build_wechat_client(settings, upstream.wechat),
        )
        result = svc.login("good", "wx_test")
        svc.check_bind_phone(result["koToken"])
        svc.bind_or_merge_phone(result["koToken"], code="phone-code")

        documented_xiaoe = {path for _m, path in xiaoe_client.ENDPOINTS.values()}
        documented_wechat = {path for _m, path in wechat_client.ENDPOINTS.values()}
        for kind, _method, url, _headers, _body in upstream.calls:
            path = url.split("?")[0].split("/", 3)[-1] if url.count("/") > 3 else url
            if kind == "xiaoe":
                hit = [p for p in documented_xiaoe if p in url]
                self.assertTrue(hit, "调了未登记的小鹅云接口：" + url)
            else:
                hit = [p for p in documented_wechat if p in url]
                self.assertTrue(hit, "调了未登记的微信接口：" + url)


class MissingCredentialTest(ApiTestBase):
    settings_overrides = {"client_id": "", "client_secret": ""}

    def test_login_reports_missing_platform_credentials(self):
        body = self.envelope(self.client.post("/api/login", json={"wx_app_id": "wx_test", "code": "good"}))
        self.assertEqual(body["code"], -1)
        self.assertIn("CLIENT_ID", body["msg"])


class HealthAndScopeTest(ApiTestBase):
    def test_health_reports_credential_flags_not_values(self):
        body = self.envelope(self.client.get("/health"))
        self.assertEqual(body["code"], 0)
        creds = body["data"]["credentials"]
        self.assertTrue(creds["clientId"] and creds["clientSecret"] and creds["sdkAppId"])
        self.assertTrue(creds["sdkSecret"])
        self.assertTrue(creds["wxAppSecret"])
        self.assertNotIn("csecret", json.dumps(body))
        self.assertNotIn("sdksecret", json.dumps(body))

    def test_removed_endpoints(self):
        config_body = self.client.get("/api/config").json()
        self.assertEqual(config_body["code"], -1)
        self.assertIn("没有这个接口", config_body["msg"])
        live_body = self.client.post("/api/live-path", json={}).json()
        self.assertEqual(live_body["code"], -1)
        self.assertIn("没有这个接口", live_body["msg"])

    def test_unknown_api_returns_envelope(self):
        body = self.envelope(self.client.get("/api/nope"))
        self.assertEqual(body["code"], -1)


class NoStaticHostingTest(ApiTestBase):
    """后端只提供 API，不托管 H5 产物。"""

    def test_root_returns_envelope_not_html(self):
        body = self.envelope(self.client.get("/"))
        self.assertEqual(body["code"], -1)
        self.assertIn("后端只提供", body["msg"])

    def test_unknown_static_path_returns_envelope(self):
        body = self.envelope(self.client.get("/assets/index.js"))
        self.assertEqual(body["code"], -1)

    def test_index_html_is_not_served(self):
        response = self.client.get("/index.html")
        self.assertIn("application/json", response.headers["content-type"])
        self.assertNotIn("<div", response.text)


class EnvConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / ".env.development").write_text(
            "PORT=8090\nXIAOE_APP_ID=app_dev\nCLIENT_ID=cid_dev\nCLIENT_SECRET=cs_dev\nSDK_APP_ID=sdk_dev\n",
            encoding="utf-8",
        )
        (root / ".env.test").write_text(
            "PORT=8091\nXIAOE_APP_ID=app_test\nCLIENT_ID=cid_test\nCLIENT_SECRET=cs_test\nSDK_APP_ID=sdk_test\nSDK_SECRET=sdk_sec_test\n",
            encoding="utf-8",
        )
        self.root = root

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_reads_only_mode_file(self):
        from app.config import load_settings

        settings = load_settings(base_dir=str(self.root), env_name="test")
        self.assertEqual(settings.port, 8091)
        self.assertEqual(settings.store_app_id, "app_test")
        self.assertEqual(settings.client_id, "cid_test")
        self.assertEqual(settings.sdk_secret, "sdk_sec_test")
        self.assertEqual(len(settings.config_files), 1)

    def test_settings_fields_are_expected(self):
        """Settings 只保留凭证、运行参数与上游路径覆盖，字段集合固定。"""
        from app.config import Settings

        self.assertEqual(
            set(Settings.__dataclass_fields__),
            {
                "port", "host", "api_base_url", "store_app_id", "client_id", "client_secret",
                "sdk_app_id", "sdk_secret", "wechat_api_base_url", "wx_app_id", "wx_app_secret",
                "request_timeout_ms", "xiaoe_paths", "wechat_paths", "openapi_server_url", "env_name",
                "config_files", "raw",
            },
        )

    def test_api_base_url_has_code_default(self):
        from app.config import load_settings

        # env 文件里没写，用代码默认值
        settings = load_settings(base_dir=str(self.root), env_name="test")
        self.assertEqual(settings.api_base_url, "https://api.xiaoe-tech.com")

        # 进程环境变量可覆盖
        os.environ["API_BASE_URL"] = "https://api.example.com/"
        try:
            settings = load_settings(base_dir=str(self.root), env_name="test")
            self.assertEqual(settings.api_base_url, "https://api.example.com")
        finally:
            os.environ.pop("API_BASE_URL", None)

    def test_xiaoe_api_base_url_is_the_canonical_key(self):
        from app.config import load_settings

        # 正式键名
        os.environ["XIAOE_API_BASE_URL"] = "https://xe.example.com/"
        try:
            settings = load_settings(base_dir=str(self.root), env_name="test")
            self.assertEqual(settings.api_base_url, "https://xe.example.com")
        finally:
            os.environ.pop("XIAOE_API_BASE_URL", None)

        # 两个键都在时，XIAOE_API_BASE_URL 优先
        os.environ["XIAOE_API_BASE_URL"] = "https://xe.example.com"
        os.environ["API_BASE_URL"] = "https://legacy.example.com"
        try:
            settings = load_settings(base_dir=str(self.root), env_name="test")
            self.assertEqual(settings.api_base_url, "https://xe.example.com")
        finally:
            os.environ.pop("XIAOE_API_BASE_URL", None)
            os.environ.pop("API_BASE_URL", None)

    def test_process_env_wins(self):
        from app.config import load_settings

        os.environ["CLIENT_SECRET"] = "from_env"
        try:
            settings = load_settings(base_dir=str(self.root), env_name="test")
            self.assertEqual(settings.client_secret, "from_env")
        finally:
            os.environ.pop("CLIENT_SECRET", None)


class UpstreamPathOverrideTest(unittest.TestCase):
    """上游接口路径可被环境变量覆盖，默认值不变。"""

    def test_defaults_come_from_endpoint_manifest(self):
        from app.services.client_service import wechat_client, xiaoe_client

        self.assertEqual(
            xiaoe_client.resolved_paths(),
            {name: path for name, (_m, path) in xiaoe_client.ENDPOINTS.items()},
        )
        self.assertEqual(
            wechat_client.resolved_paths(),
            {name: path for name, (_m, path) in wechat_client.ENDPOINTS.items()},
        )

    def test_override_wins_and_unknown_names_are_ignored(self):
        from app.services.client_service import xiaoe_client

        paths = xiaoe_client.resolved_paths(
            {"token": "/token/v2", "register": "xe.user.register/2.0.0", "notAnEndpoint": "/nope"}
        )
        self.assertEqual(paths["token"], "/token/v2")
        # 不带前导斜杠时自动补上
        self.assertEqual(paths["register"], "/xe.user.register/2.0.0")
        # 拼错的键既不会把接口打成空路径，也不会凭空多出一个接口
        self.assertNotIn("notAnEndpoint", paths)
        self.assertEqual(len(paths), len(xiaoe_client.ENDPOINTS))

    def test_override_actually_changes_the_request_url(self):
        from app.services.client_service.xiaoe_client import XiaoeClient, XiaoeConfig

        calls = []

        def fake_transport(url, method, headers, body, timeout):
            calls.append((method, url))
            return 200, json.dumps({"code": 0, "data": {"access_token": "at", "expires_in": 7200}})

        client = XiaoeClient(
            XiaoeConfig(
                api_base_url="https://api.example.com",
                app_id="app_test",
                client_id="cid",
                client_secret="csecret",
                sdk_app_id="sdkapp",
                paths={"token": "/open/token/v2"},
            ),
            transport=fake_transport,
        )
        self.assertEqual(client.get_access_token(), "at")
        self.assertEqual(calls[0][0], "GET")
        self.assertIn("https://api.example.com/open/token/v2?", calls[0][1])

    def test_settings_read_overrides_from_env(self):
        from app.config import load_settings

        with tempfile.TemporaryDirectory() as root:
            os.environ["API_PATH_TOKEN"] = "/env/token"
            os.environ["WX_PATH_JSCODE2SESSION"] = "/env/jscode"
            try:
                settings = load_settings(base_dir=root, env_name="test")
            finally:
                os.environ.pop("API_PATH_TOKEN", None)
                os.environ.pop("WX_PATH_JSCODE2SESSION", None)
        self.assertEqual(settings.xiaoe_paths, {"token": "/env/token"})
        self.assertEqual(settings.wechat_paths, {"jscode2session": "/env/jscode"})

    def test_no_override_configured_by_default(self):
        from app.config import load_settings

        with tempfile.TemporaryDirectory() as root:
            settings = load_settings(base_dir=root, env_name="test")
        self.assertEqual(settings.xiaoe_paths, {})
        self.assertEqual(settings.wechat_paths, {})


class HealthUpstreamsTest(ApiTestBase):
    settings_overrides = {"xiaoe_paths": {"token": "/overridden/token"}}

    def test_health_exposes_resolved_upstreams(self):
        body = self.envelope(self.client.get("/health"))
        upstreams = body["data"]["upstreams"]
        # 覆盖项生效，未覆盖项仍是默认路径
        self.assertEqual(upstreams["xiaoe"]["token"], "GET /overridden/token")
        self.assertEqual(upstreams["xiaoe"]["register"], "POST /xe.user.register/1.0.0")
        self.assertEqual(upstreams["wechat"]["jscode2session"], "GET /sns/jscode2session")
        self.assertEqual(upstreams["overridden"], ["xiaoe.token"])

    def test_override_also_applies_to_real_login_calls(self):
        body = self.envelope(self.client.post("/api/login", json={"wx_app_id": "wx_test", "code": "good"}))
        self.assertEqual(body["code"], 0)
        urls = [call[2] for call in self.upstream.calls]
        self.assertTrue([u for u in urls if "/overridden/token" in u], "登录没走覆盖后的 /overridden/token")


class ChineseDocsPageTest(ApiTestBase):
    """自定义的中文接口文档页（/api/docs）。"""

    def test_docs_page_renders_with_chinese_labels(self):
        response = self.client.get("/api/docs")
        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn("接口文档", html)
        # 文案映射表随页面下发（在线调试/发送请求/数据模型…）
        for label in ("在线调试", "发送请求", "数据模型", "响应体"):
            self.assertIn(label, html)
        # 数据仍然来自标准 openapi.json
        self.assertIn("/api/openapi.json", html)

    def test_swagger_ui_version_is_pinned(self):
        from app.http.docs_page import SWAGGER_UI_VERSION

        html = self.client.get("/api/docs").text
        self.assertIn("swagger-ui-dist@" + SWAGGER_UI_VERSION, html)

    def test_docs_page_not_in_schema(self):
        spec = self.client.get("/api/openapi.json").json()
        self.assertNotIn("/api/docs", spec["paths"])


class OpenApiSpecComplianceTest(ApiTestBase):
    """按 OpenAPI 3.0 规范输出，能被 Apifox / Postman 正常导入。"""

    def spec(self):
        return self.client.get("/api/openapi.json").json()

    def test_version_is_30(self):
        # FastAPI 默认吐 3.1.0，工具支持不全，这里固定降级成 3.0.3
        self.assertEqual(self.spec()["openapi"], "3.0.3")

    def test_no_openapi_31_only_constructs(self):
        from app.http.openapi30 import count_31_markers

        self.assertEqual(count_31_markers(self.spec()), [])

    def test_nullable_used_for_optional_data(self):
        data = self.spec()["components"]["schemas"]["Envelope_LoginData_"]["properties"]["data"]
        self.assertTrue(data.get("nullable"), "Optional 字段应转成 nullable: true")
        self.assertIn("$ref", data)

    def test_servers_declared(self):
        servers = self.spec().get("servers") or []
        self.assertTrue(servers, "缺 servers 时导入工具拿不到基础地址")
        self.assertEqual(servers[0]["url"], "https://example.test")

    def test_operation_ids_unique_and_stable(self):
        ids = [
            op["operationId"]
            for ops in self.spec()["paths"].values()
            for op in ops.values()
        ]
        self.assertEqual(len(ids), len(set(ids)), "operationId 必须唯一")
        for expected in ("login", "sessionCheck", "checkBindPhone", "bindOrMergePhone", "loginUrl", "profile"):
            self.assertIn(expected, ids)


class OpenApiContractTest(ApiTestBase):
    """接口文档（/api/docs 背后的 openapi.json）要能当契约用。"""

    ENDPOINTS = {
        "/api/login",
        "/api/session/check",
        "/api/check-bind-phone",
        "/api/bind-or-merge-phone",
        "/api/login-url",
        "/api/profile",
    }

    def spec(self):
        response = self.client.get("/api/openapi.json")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_every_api_documents_envelope_schema(self):
        spec = self.spec()
        for path in self.ENDPOINTS:
            op = spec["paths"][path]["post"]
            schema = op["responses"]["200"]["content"]["application/json"]["schema"]
            self.assertIn("$ref", schema, path + " 的 200 响应缺 schema")
            self.assertTrue(schema["$ref"].startswith("#/components/schemas/Envelope_"), path)

    def test_health_documents_envelope_schema(self):
        spec = self.spec()
        for op in spec["paths"]["/health"].values():
            schema = op["responses"]["200"]["content"]["application/json"]["schema"]
            self.assertTrue(schema.get("$ref", "").startswith("#/components/schemas/Envelope_HealthData_"))

    def test_data_models_and_examples_exist(self):
        spec = self.spec()
        schemas = spec["components"]["schemas"]
        for name in ("LoginData", "SessionCheckData", "ProfileData", "BindPhoneData", "LoginUrlData", "HealthData"):
            self.assertIn(name, schemas)
        # 契约里带示例，Swagger 里能直接看到长什么样
        self.assertIn("example", json.dumps(schemas["LoginData"]))

    def test_fallback_routes_are_not_in_schema(self):
        spec = self.spec()
        for path in spec["paths"]:
            self.assertNotIn("{rest}", path, "兜底 404 路由不应出现在接口文档里")

    def test_tags_and_summaries(self):
        spec = self.spec()
        self.assertEqual({t["name"] for t in spec["tags"]}, {"登录与登录态", "运维"})
        self.assertEqual(spec["paths"]["/api/login"]["post"]["summary"], "小程序登录")
        self.assertEqual(spec["paths"]["/health"]["get"]["tags"], ["运维"])


if __name__ == "__main__":
    unittest.main()
