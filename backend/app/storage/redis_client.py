# -*- coding: utf-8 -*-
"""
Redis 客户端封装
提供缓存、会话管理等基础功能
"""

import json
from typing import Any, Optional
import redis
from app.config.settings import settings
from app.core.logger import get_logger

logger = get_logger("redis")


class RedisClient:
    """Redis 客户端封装"""

    def __init__(self):
        self._client = None
        self._connect()

    def _connect(self):
        """建立 Redis 连接"""
        try:
            self._client = redis.from_url(
                settings.redis_url,
                decode_responses=True,  # 自动解码为字符串
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            # 测试连接
            self._client.ping()
            logger.info(f"Redis 连接成功: {settings.redis_url}")
        except Exception as e:
            logger.error(f"Redis 连接失败: {e}")
            self._client = None

    @property
    def client(self) -> Optional[redis.Redis]:
        """获取 Redis 客户端实例"""
        if self._client is None:
            self._connect()
        return self._client

    def is_connected(self) -> bool:
        """检查 Redis 是否连接"""
        try:
            if self._client:
                self._client.ping()
                return True
        except Exception:
            pass
        return False

    # ── 基础操作 ──────────────────────────────────────

    def get(self, key: str) -> Optional[str]:
        """获取字符串值"""
        try:
            if self.client:
                return self.client.get(key)
        except Exception as e:
            logger.warning(f"Redis GET 失败: {key}: {e}")
        return None

    def set(
        self,
        key: str,
        value: str,
        ex: Optional[int] = None,
    ) -> bool:
        """
        设置字符串值

        Args:
            key: 键
            value: 值
            ex: 过期时间（秒）
        """
        try:
            if self.client:
                self.client.set(key, value, ex=ex)
                return True
        except Exception as e:
            logger.warning(f"Redis SET 失败: {key}: {e}")
        return False

    def delete(self, key: str) -> bool:
        """删除键"""
        try:
            if self.client:
                self.client.delete(key)
                return True
        except Exception as e:
            logger.warning(f"Redis DELETE 失败: {key}: {e}")
        return False

    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        try:
            if self.client:
                return self.client.exists(key) > 0
        except Exception as e:
            logger.warning(f"Redis EXISTS 失败: {key}: {e}")
        return False

    # ── JSON 操作 ─────────────────────────────────────

    def get_json(self, key: str) -> Optional[Any]:
        """获取 JSON 值"""
        data = self.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError as e:
                logger.error(f"Redis JSON 解析失败: {key}, {e}")
        return None

    def set_json(
        self,
        key: str,
        value: Any,
        ex: Optional[int] = None,
    ) -> bool:
        """设置 JSON 值"""
        try:
            return self.set(key, json.dumps(value, ensure_ascii=False), ex=ex)
        except Exception as e:
            logger.error(f"Redis JSON 序列化失败: {key}, {e}")
            return False

    # ── 缓存装饰器辅助 ────────────────────────────────

    def cache_get(self, prefix: str, key: str) -> Optional[Any]:
        """获取缓存"""
        return self.get_json(f"{prefix}:{key}")

    def cache_set(
        self,
        prefix: str,
        key: str,
        value: Any,
        ex: int = 3600,
    ) -> bool:
        """设置缓存，默认 1 小时过期"""
        return self.set_json(f"{prefix}:{key}", value, ex=ex)

    def cache_delete(self, prefix: str, key: str) -> bool:
        """删除缓存"""
        return self.delete(f"{prefix}:{key}")

    def cache_clear_prefix(self, prefix: str) -> int:
        """清除指定前缀的所有缓存（使用 SCAN 避免阻塞 Redis）"""
        try:
            if self.client:
                deleted = 0
                cursor = 0
                while True:
                    cursor, keys = self.client.scan(
                        cursor=cursor, match=f"{prefix}:*", count=100
                    )
                    if keys:
                        deleted += self.client.delete(*keys)
                    if cursor == 0:
                        break
                return deleted
        except Exception as e:
            logger.warning(f"Redis 清除缓存失败: {prefix}:*: {e}")
        return 0


# 全局单例
redis_client = RedisClient()
