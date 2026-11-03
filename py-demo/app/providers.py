"""全局组件单例：配置与日志。"""
from __future__ import annotations

import logging
from typing import Optional

from app.config import Settings, load_settings

_settings: Optional[Settings] = None
_logger: Optional[logging.Logger] = None


def init_providers(settings: Optional[Settings] = None) -> Settings:
    """初始化配置与日志，返回 settings。"""
    global _settings, _logger
    _settings = settings or load_settings()
    if _logger is None:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s\t%(levelname)s\t%(name)s\t%(message)s", "%Y-%m-%dT%H:%M:%S%z")
        )
        logger = logging.getLogger("app")
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        logger.propagate = False
        _logger = logger
    return _settings


def settings() -> Settings:
    if _settings is None:
        return init_providers()
    return _settings


def logger() -> logging.Logger:
    if _logger is None:
        init_providers()
    assert _logger is not None
    return _logger
