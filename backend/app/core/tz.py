"""
统一时区工具
项目中所有时间操作统一使用东八区（CST, UTC+8）时间
"""

from datetime import datetime, timezone, timedelta

# 东八区时区常量
CST = timezone(timedelta(hours=8))


def now_cst() -> datetime:
    """
    获取当前东八区时间（naive datetime，不含 tzinfo）

    用于：
    - 数据库模型字段的 default 值
    - 业务逻辑中需要记录时间的场景

    返回 naive datetime 是为了与 SQLAlchemy Column(DateTime) 兼容，
    存储的值已经是东八区本地时间。
    """
    return datetime.now(CST).replace(tzinfo=None)
