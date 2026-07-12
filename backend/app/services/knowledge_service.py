"""
知识库服务模块
提供文档分块、向量化、存储和检索功能
使用 PgVector 作为向量存储
"""

import asyncio
from typing import List, Dict, Any
from pathlib import Path

from app.config.settings import settings
from app.core.logger import get_logger

logger = get_logger("knowledge_service")


class KnowledgeService:
    """知识库服务类"""

    def __init__(self):
        self.embeddings = None
        self.vector_store = None
        self.text_splitter = None
        self._initialized = False

    def _initialize(self):
        """延迟初始化，避免启动时加载依赖"""
        if self._initialized:
            return

        try:
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            from langchain_openai import OpenAIEmbeddings

            # 初始化 Embeddings
            self.embeddings = OpenAIEmbeddings(
                openai_api_key=settings.OPENAI_API_KEY, openai_api_base=settings.OPENAI_BASE_URL
            )

            # 初始化文本分割器
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
                separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " "],
            )

            # 初始化向量存储
            self._init_vector_store()

            self._initialized = True
            logger.info("知识库服务初始化完成")

        except Exception as e:
            logger.error(f"知识库服务初始化失败: {e}")
            raise

    def _init_vector_store(self):
        """初始化向量存储"""
        try:
            from langchain_community.vectorstores import PGVector

            # 构建连接字符串
            connection_string = settings.database_url

            self.vector_store = PGVector(
                connection_string=connection_string,
                embedding_function=self.embeddings,
                collection_name="knowledge_base",
                pre_delete_collection=False,
            )

            logger.info("PgVector 向量存储初始化完成")

        except Exception as e:
            logger.error(f"向量存储初始化失败: {e}")
            raise

    def load_document(self, file_path: str) -> List[Any]:
        """
        加载文档

        Args:
            file_path: 文件路径

        Returns:
            文档列表
        """
        self._initialize()

        try:
            from langchain_community.document_loaders import (
                PyPDFLoader,
                TextLoader,
                UnstructuredMarkdownLoader,
            )

            file_ext = Path(file_path).suffix.lower()

            # 根据文件类型选择加载器
            if file_ext == ".pdf":
                loader = PyPDFLoader(file_path)
            elif file_ext == ".md":
                loader = UnstructuredMarkdownLoader(file_path)
            elif file_ext in [".txt", ".text"]:
                loader = TextLoader(file_path, encoding="utf-8")
            else:
                logger.warning(f"不支持的文件类型: {file_ext}")
                return []

            documents = loader.load()
            logger.info(f"加载文档成功: {file_path}, 页数={len(documents)}")
            return documents

        except Exception as e:
            logger.error(f"加载文档失败 {file_path}: {e}")
            return []

    def split_document(self, documents: List[Any]) -> List[Any]:
        """
        文档分块

        Args:
            documents: 文档列表

        Returns:
            分块后的文档列表
        """
        self._initialize()

        try:
            chunks = self.text_splitter.split_documents(documents)
            logger.info(f"文档分块完成: 原始={len(documents)}, 分块后={len(chunks)}")
            return chunks

        except Exception as e:
            logger.error(f"文档分块失败: {e}")
            return []

    async def embed_and_store(self, file_path: str) -> int:
        """
        加载文档、分块、向量化并存储

        Args:
            file_path: 文件路径

        Returns:
            存储的文档块数量
        """
        import asyncio

        self._initialize()

        try:
            # 加载文档（同步阻塞操作，委托到线程池）
            documents = await asyncio.to_thread(self.load_document, file_path)
            if not documents:
                return 0

            # 分块
            chunks = await asyncio.to_thread(self.split_document, documents)
            if not chunks:
                return 0

            # 添加元数据
            for chunk in chunks:
                chunk.metadata["source"] = file_path
                chunk.metadata["file_name"] = Path(file_path).name

            # 存储到向量库（同步阻塞操作，委托到线程池）
            await asyncio.to_thread(self.vector_store.add_documents, chunks)

            logger.info(f"文档存储完成: {file_path}, 块数={len(chunks)}")
            return len(chunks)

        except Exception as e:
            logger.error(f"文档存储失败 {file_path}: {e}")
            return 0

    async def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        检索相似文档

        Args:
            query: 查询文本
            k: 返回结果数量

        Returns:
            检索结果列表
        """
        self._initialize()

        try:
            # 执行相似性搜索（同步操作，委托到线程池避免阻塞事件循环）
            results = await asyncio.to_thread(
                self.vector_store.similarity_search_with_score, query, k=k
            )

            formatted_results = []
            for doc, score in results:
                formatted_results.append(
                    {"content": doc.page_content, "metadata": doc.metadata, "score": float(score)}
                )

            logger.info(f"知识库检索完成: query='{query[:50]}...', 结果数={len(formatted_results)}")
            return formatted_results

        except Exception as e:
            logger.error(f"知识库检索失败: {e}")
            return []

    async def delete_by_source(self, file_path: str) -> bool:
        """
        删除指定来源的文档

        Args:
            file_path: 文件路径

        Returns:
            是否成功删除
        """
        self._initialize()

        try:
            import asyncio
            from sqlalchemy import text
            from app.database.session import engine

            def _do_delete():
                with engine.connect() as conn:
                    query = text("""
                        DELETE FROM langchain_pg_embedding
                        WHERE cmetadata->>'source' = :source
                    """)
                    conn.execute(query, {"source": file_path})
                    conn.commit()

            await asyncio.to_thread(_do_delete)
            logger.info(f"删除文档成功: {file_path}")
            return True

        except Exception as e:
            logger.error(f"删除文档失败 {file_path}: {e}")
            return False

    async def get_collection_stats(self) -> Dict[str, Any]:
        """
        获取知识库统计信息

        Returns:
            统计信息
        """
        import asyncio

        self._initialize()

        try:
            from sqlalchemy import text
            from app.database.session import engine

            def _query_stats():
                with engine.connect() as conn:
                    count_query = text("SELECT COUNT(*) FROM langchain_pg_embedding")
                    count = conn.execute(count_query).scalar() or 0

                    source_query = text("""
                        SELECT cmetadata->>'source' as source, COUNT(*) as count
                        FROM langchain_pg_embedding
                        GROUP BY cmetadata->>'source'
                    """)
                    result = conn.execute(source_query)
                    sources = [{"source": row[0], "count": row[1]} for row in result]

                return {"total_chunks": count, "sources": sources}

            return await asyncio.to_thread(_query_stats)

        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {"total_chunks": 0, "sources": []}


# 全局知识库服务实例
knowledge_service = KnowledgeService()
