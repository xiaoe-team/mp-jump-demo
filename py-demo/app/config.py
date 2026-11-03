"""配置读取：进程环境变量 > .env.<env> > 代码默认值。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


def _parse_env_file(path: str) -> Dict[str, str]:
    """解析极简 .env：KEY=VALUE、# 注释、成对引号。"""
    values: Dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as fp:
            for raw in fp:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                idx = line.find("=")
                if idx <= 0:
                    continue
                key = line[:idx].strip()
                val = line[idx + 1 :].strip()
                if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
                    val = val[1:-1]
                values[key] = val
    except OSError:
        pass
    return values


@dataclass
class Settings:
    """运行配置。"""

    port: int = 8090
    host: str = "0.0.0.0"
    # ===== 小鹅云开放平台（自己实现登录所需的店铺级凭证）=====
    api_base_url: str = "https://api.xiaoe-tech.com"
    store_app_id: str = ""
    client_id: str = ""
    client_secret: str = ""
    sdk_app_id: str = ""
    sdk_secret: str = ""
    # ===== 微信小程序 =====
    wechat_api_base_url: str = "https://api.weixin.qq.com"
    wx_app_id: str = ""
    wx_app_secret: str = ""
    request_timeout_ms: int = 10000
    # 接口路径覆盖（键名见 XIAOE_PATH_ENV / WECHAT_PATH_ENV；空表示全部用默认路径）
    xiaoe_paths: Dict[str, str] = field(default_factory=dict)
    wechat_paths: Dict[str, str] = field(default_factory=dict)
    # 接口文档里的 servers 地址（Apifox 等工具导入时用它当基础地址；空表示不写 servers）
    openapi_server_url: str = ""
    env_name: str = "development"
    config_files: List[str] = field(default_factory=list)
    raw: Dict[str, str] = field(default_factory=dict)

    @property
    def config_file(self) -> str:
        return ", ".join(self.config_files) if self.config_files else "(env only)"

    def credential_status(self) -> Dict[str, bool]:
        """凭证是否齐全（只回显布尔，不暴露值）。"""
        return {
            "storeAppId": bool(self.store_app_id),
            "clientId": bool(self.client_id),
            "clientSecret": bool(self.client_secret),
            "sdkAppId": bool(self.sdk_app_id),
            "sdkSecret": bool(self.sdk_secret),
            "wxAppId": bool(self.wx_app_id),
            "wxAppSecret": bool(self.wx_app_secret),
            "apiBaseUrl": bool(self.api_base_url),
            "wechatApiBaseUrl": bool(self.wechat_api_base_url),
        }

DEFAULT_ENV = "development"

# ===== 上游接口路径的环境变量名 =====
# 值名对应各自 client 里 ENDPOINTS 的键；默认路径写在 client 模块（唯一来源），
# 这里只声明「哪个环境变量能覆盖哪个接口」，不重复维护默认值。
# 覆盖用途：小鹅云接口版本升级（/xe.user.register/1.0.0 → 新版本）、
# 指向沙箱/预发上游、临时排查时改路径，都不需要改代码重新发版。
XIAOE_PATH_ENV: Dict[str, str] = {
    "token": "API_PATH_TOKEN",
    "register": "API_PATH_USER_REGISTER",
    "sdkLogin": "API_PATH_SDK_ACCOUNT_LOGIN",
    "userInfo": "API_PATH_USER_INFO_GET",
    "bindOrMergePhone": "API_PATH_BIND_OR_MERGE_PHONE",
    "loginUrl": "API_PATH_LOGIN_URL",
}

WECHAT_PATH_ENV: Dict[str, str] = {
    "jscode2session": "WX_PATH_JSCODE2SESSION",
    "stableToken": "WX_PATH_STABLE_TOKEN",
    "getPhoneNumber": "WX_PATH_GET_PHONE_NUMBER",
}


def resolve_env_name(explicit: Optional[str] = None) -> str:
    """环境名：显式参数 > APP_ENV 环境变量 > development。"""
    if explicit:
        return str(explicit).strip()
    return (os.environ.get("APP_ENV") or DEFAULT_ENV).strip() or DEFAULT_ENV


def load_settings(env_file: Optional[str] = None, base_dir: Optional[str] = None, env_name: Optional[str] = None) -> Settings:
    """载入配置。

    只读 .env.<env_name>（每个环境文件都写全所有变量，不再有基线 .env 兜底），
    进程环境变量优先级最高。env_file 显式指定时只读该文件。
    """
    base = base_dir or os.getcwd()
    name = resolve_env_name(env_name)

    if env_file:
        candidates = [env_file]
    else:
        candidates = [".env.%s" % name]

    file_values: Dict[str, str] = {}
    loaded: List[str] = []
    for candidate in candidates:
        path = candidate if os.path.isabs(candidate) else os.path.join(base, candidate)
        if not os.path.exists(path):
            continue
        file_values.update(_parse_env_file(path))
        loaded.append(path)

    def get(key: str, default: str = "") -> str:
        if os.environ.get(key, "").strip():
            return os.environ[key].strip()
        return (file_values.get(key) or default).strip()

    def get_int(key: str, default: int) -> int:
        try:
            return int(get(key, str(default)))
        except (TypeError, ValueError):
            return default

    def collect_paths(env_keys: Dict[str, str]) -> Dict[str, str]:
        """收「有值的」路径覆盖项；没配就留空，交给 client 用默认路径。"""
        result: Dict[str, str] = {}
        for name, env_key in env_keys.items():
            value = get(env_key, "")
            if value:
                result[name] = value
        return result

    return Settings(
        port=get_int("PORT", 8090),
        host=get("HOST", "0.0.0.0"),
        api_base_url=(
            get("XIAOE_API_BASE_URL", "")
            # 兼容旧键名 API_BASE_URL（早期文档与部署脚本用的是这个）
            or get("API_BASE_URL", "https://api.xiaoe-tech.com")
        ).rstrip("/"),
        # 店铺 ID：XIAOE_APP_ID（前端对应变量为 VITE_XIAOE_APP_ID）
        store_app_id=get("XIAOE_APP_ID", ""),
        client_id=get("CLIENT_ID", ""),
        client_secret=get("CLIENT_SECRET", ""),
        sdk_app_id=get("SDK_APP_ID", ""),
        sdk_secret=get("SDK_SECRET", ""),
        wechat_api_base_url=get("WECHAT_API_BASE_URL", "https://api.weixin.qq.com").rstrip("/"),
        wx_app_id=get("WX_APP_ID", ""),
        wx_app_secret=get("WX_APP_SECRET", ""),
        request_timeout_ms=get_int("REQUEST_TIMEOUT_MS", 10000),
        xiaoe_paths=collect_paths(XIAOE_PATH_ENV),
        wechat_paths=collect_paths(WECHAT_PATH_ENV),
        openapi_server_url=get("OPENAPI_SERVER_URL", "").rstrip("/"),
        env_name=name,
        config_files=loaded,
        raw=file_values,
    )
