"""
API 请求限流配置
使用 slowapi 实现，按客户端 IP 进行限流
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# 全局限流器实例，通过 IP 地址识别客户端
limiter = Limiter(key_func=get_remote_address)
