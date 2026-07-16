"""
知识库 API 路由
提供文档上传、检索、统计等独立端点
"""

import os
import tempfile

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.core.security import get_current_user, RequirePermission
from app.core.logger import get_logger
from app.database.session import get_db
from app.entity.db_models import User
from app.entity.schemas import ApiResponse, DeleteDocumentRequest
from app.services.knowledge_service import knowledge_service

logger = get_logger("knowledge_api")

router = APIRouter(prefix="/api/knowledge", tags=["知识库"])


@router.post("/upload", response_model=ApiResponse, dependencies=[Depends(RequirePermission("knowledge:manage"))])
async def upload_document(
    file: UploadFile = File(..., description="文档文件 (PDF/MD/TXT)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    上传文档到知识库

    支持的文件类型：PDF、Markdown、TXT
    文档会被自动分块、向量化并存储到 PgVector
    """
    # 检查文件类型
    allowed_extensions = [".pdf", ".md", ".txt", ".text"]
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {file_ext}，支持: {', '.join(allowed_extensions)}",
        )

    # 保存临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # 上传到知识库
        chunks_count = await knowledge_service.embed_and_store(tmp_path)

        if chunks_count == 0:
            raise HTTPException(status_code=400, detail="文档处理失败，未生成有效内容")

        logger.info(
            f"用户 {current_user.username} 上传文档: {file.filename}, 分块数={chunks_count}"
        )

        return ApiResponse(
            code=200,
            message="文档上传成功",
            data={"filename": file.filename, "chunks_count": chunks_count},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文档上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"文档上传失败: {str(e)}")
    finally:
        # 清理临时文件
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get("/search", response_model=ApiResponse, dependencies=[Depends(RequirePermission("knowledge:search"))])
async def search_knowledge(
    query: str = ...,
    k: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    检索知识库

    Args:
        query: 查询文本
        k: 返回结果数量（默认5）
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="查询内容不能为空")

    try:
        results = await knowledge_service.search(query, k=k)

        return ApiResponse(
            code=200, data={"query": query, "results": results, "total": len(results)}
        )

    except Exception as e:
        logger.error(f"知识库检索失败: {e}")
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")


@router.get("/stats", response_model=ApiResponse, dependencies=[Depends(RequirePermission("knowledge:search"))])
async def get_knowledge_stats(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """获取知识库统计信息"""
    try:
        stats = await knowledge_service.get_collection_stats()

        return ApiResponse(code=200, data=stats)

    except Exception as e:
        logger.error(f"获取知识库统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")


@router.delete("/", response_model=ApiResponse, dependencies=[Depends(RequirePermission("knowledge:manage"))])
async def delete_document(
    request: DeleteDocumentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    删除指定来源的文档

    Args:
        request: 删除文档请求体，包含文档来源
    """
    source = request.source
    if not source.strip():
        raise HTTPException(status_code=400, detail="文档来源不能为空")

    try:
        success = await knowledge_service.delete_by_source(source)

        if not success:
            raise HTTPException(status_code=404, detail="未找到指定文档")

        logger.info(f"用户 {current_user.username} 删除文档: {source}")

        return ApiResponse(code=200, message="文档删除成功")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文档失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
