"""
路径安全校验工具
校验文件/目录路径是否在白名单目录内，防止路径穿越攻击
"""

from pathlib import Path

from fastapi import HTTPException

from app.config.settings import settings


def validate_path(file_path: str, allowed_dirs_str: str, label: str = "路径") -> None:
    """
    校验路径是否在白名单目录内

    Args:
        file_path: 待校验的文件/目录路径
        allowed_dirs_str: 白名单目录字符串（逗号分隔）
        label: 路径标签（用于错误提示）

    Raises:
        HTTPException: 路径不在白名单内
    """
    resolved = Path(file_path).resolve()
    allowed_dirs = [d.strip() for d in allowed_dirs_str.split(",") if d.strip()]
    for allowed in allowed_dirs:
        try:
            resolved.relative_to(Path(allowed).resolve())
            return  # 路径在白名单内
        except ValueError:
            continue
    raise HTTPException(
        status_code=400,
        detail=f"{label}不在允许的目录内，允许的目录: {', '.join(allowed_dirs)}",
    )


def validate_training_path(file_path: str, label: str = "路径") -> None:
    """校验训练相关路径"""
    validate_path(file_path, settings.ALLOWED_TRAINING_DIRS, label)


def validate_detection_path(file_path: str, label: str = "路径") -> None:
    """校验检测相关路径"""
    validate_path(file_path, settings.ALLOWED_DETECTION_DIRS, label)
