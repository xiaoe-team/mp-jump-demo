"""进程内登录态表：ko_token → user_id，带过期时间（本项目不使用 Redis）。"""
from __future__ import annotations

import threading
import time
from typing import Dict, Optional, Tuple


class MemorySessionStore:
    """线程安全的内存会话表；进程重启即清空。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._data: Dict[str, Tuple[str, float]] = {}

    def save(self, token: str, user_id: str, expires_in: int) -> None:
        if not token or not user_id:
            return
        ttl = int(expires_in) if int(expires_in) > 0 else 7200
        with self._lock:
            self._purge_locked()
            self._data[token] = (user_id, time.time() + ttl)

    def get_user_id(self, token: str) -> Optional[str]:
        if not token:
            return None
        with self._lock:
            item = self._data.get(token)
            if not item:
                return None
            user_id, expire_at = item
            if expire_at <= time.time():
                self._data.pop(token, None)
                return None
            return user_id

    def remove(self, token: str) -> None:
        with self._lock:
            self._data.pop(token, None)

    def size(self) -> int:
        with self._lock:
            self._purge_locked()
            return len(self._data)

    def _purge_locked(self) -> None:
        now = time.time()
        for token in [t for t, (_uid, exp) in self._data.items() if exp <= now]:
            self._data.pop(token, None)


# 进程级单例：路由每次请求都会新建 LoginService，会话表必须共享
default_store = MemorySessionStore()


class PhoneIntentStore:
    """手机号绑定/合并意图：bind_token → (user_id, phone)，10 分钟有效、一次性。"""

    def __init__(self, ttl_seconds: int = 600):
        self._lock = threading.Lock()
        self._ttl = ttl_seconds
        self._data: Dict[str, Tuple[str, str, float]] = {}

    def create(self, user_id: str, phone: str) -> str:
        import secrets

        token = secrets.token_urlsafe(24)
        with self._lock:
            self._purge_locked()
            self._data[token] = (user_id, phone, time.time() + self._ttl)
        return token

    def consume(self, token: str) -> Optional[Tuple[str, str]]:
        if not token:
            return None
        with self._lock:
            item = self._data.pop(token, None)
            if not item:
                return None
            user_id, phone, expire_at = item
            if expire_at <= time.time():
                return None
            return user_id, phone

    def _purge_locked(self) -> None:
        now = time.time()
        for token in [t for t, (_u, _p, exp) in self._data.items() if exp <= now]:
            self._data.pop(token, None)


# 进程级单例：路由每次请求都会新建 LoginService，会话与绑定意图必须共享
default_store = MemorySessionStore()
default_phone_intents = PhoneIntentStore()
