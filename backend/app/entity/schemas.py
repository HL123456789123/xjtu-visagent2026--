"""
Pydantic 请求/响应模型
用于 API 接口的数据验证和序列化
分层原则：
- Create 模型：创建资源时的请求体
- Update 模型：更新资源时的请求体（所有字段可选）
- Response 模型：API 返回的响应体（过滤敏感字段）
- List 模型：分页列表查询的参数和响应
"""

from datetime import datetime
from typing import Literal, Optional, Union
from pydantic import BaseModel, Field, EmailStr


# ══════════════════════════════════════════════════════════════
# 一、用户与权限
# ══════════════════════════════════════════════════════════════

# --- 认证相关 ---


class UserRegister(BaseModel):
    """用户注册请求"""

    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=100, description="密码")


class UserLogin(BaseModel):
    """用户登录请求"""

    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class UserBrief(BaseModel):
    """用户简要信息（嵌入在 Token 响应中）"""

    id: int
    username: str
    email: str
    avatar: Optional[str] = None
    is_superuser: bool = False
    roles: list[str] = []
    permissions: list[str] = []

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """登录成功响应"""

    access_token: str
    token_type: str = "bearer"
    user: UserBrief


# --- 用户管理 ---


class UserResponse(BaseModel):
    """用户详情响应"""

    id: int
    username: str
    email: str
    phone: Optional[str] = None
    avatar: Optional[str] = None
    is_active: bool
    is_superuser: bool = False
    roles: list[str] = []
    permissions: list[str] = []
    last_login_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """用户信息更新"""

    phone: Optional[str] = None
    avatar: Optional[str] = None
    email: Optional[str] = None


class ChangePassword(BaseModel):
    """修改密码"""

    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")


# --- 角色权限 ---


class RoleResponse(BaseModel):
    """角色响应"""

    id: int
    name: str
    display_name: str
    description: Optional[str] = None
    is_system: bool
    permissions: list[str] = []
    user_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleCreate(BaseModel):
    """创建角色"""

    name: str = Field(..., min_length=2, max_length=50, description="角色标识")
    display_name: str = Field(..., description="角色显示名")
    description: Optional[str] = None
    permission_codes: list[str] = Field(default=[], description="权限编码列表")


class RoleUpdate(BaseModel):
    """更新角色"""

    display_name: Optional[str] = None
    description: Optional[str] = None
    permission_codes: Optional[list[str]] = None


class RolePermissionAssign(BaseModel):
    """分配角色权限"""

    permission_codes: list[str] = Field(..., description="权限编码列表")


class PermissionResponse(BaseModel):
    """权限响应"""

    id: int
    code: str
    name: str
    module: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class PermissionGroupResponse(BaseModel):
    """按模块分组的权限响应"""

    module: str
    permissions: list[PermissionResponse]


# --- 管理员用户管理 ---


class UserAdminCreate(BaseModel):
    """管理员创建普通用户"""

    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=100, description="初始密码")


class UserAdminUpdate(BaseModel):
    """管理员修改用户信息"""

    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None


class UserRoleAssign(BaseModel):
    """分配用户角色"""

    role_ids: list[int] = Field(..., description="角色 ID 列表")


class UserRoleUpdate(BaseModel):
    """设置用户身份（管理员或普通用户）"""

    role: Literal["admin", "user"] = Field(..., description="用户身份")


class UserStatusUpdate(BaseModel):
    """启用/禁用用户"""

    is_active: bool = Field(..., description="是否启用")


# ══════════════════════════════════════════════════════════════
# 二、检测模块
# ══════════════════════════════════════════════════════════════


class DetectionSceneResponse(BaseModel):
    """检测场景响应"""
    id: int
    name: str
    display_name: str
    description: Optional[str] = None
    category: str
    class_names: list[str]
    class_names_cn: Optional[dict] = None
    is_active: bool = True
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DetectionTaskResponse(BaseModel):
    """检测任务响应"""
    id: int
    user_id: int
    scene_id: int
    model_version_id: Optional[int] = None
    task_type: str
    status: str
    total_images: int = 0
    total_objects: int = 0
    total_inference_time: float = 0
    conf_threshold: float = 0.25
    iou_threshold: float = 0.45
    image_size: int = 640
    error_message: Optional[str] = None
    analysis_report: Optional[str] = None
    risk_level: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DetectionResultResponse(BaseModel):
    """检测结果响应"""
    id: int
    task_id: int
    image_path: str
    annotated_image_url: Optional[str] = None
    class_name: str
    class_name_cn: Optional[str] = None
    class_id: int
    confidence: float
    bbox: list
    inference_time: Optional[float] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════
# 三、训练模块
# ══════════════════════════════════════════════════════════════


class TrainingTaskResponse(BaseModel):
    """训练任务响应"""
    id: int
    user_id: int
    model_id: Optional[int] = None
    task_uuid: str
    status: str
    base_architecture: str = "yolo26n"
    epochs: int = 100
    current_epoch: int = 0
    progress: int = 0
    img_size: int = 640
    batch_size: int = 16
    device: str = "0"
    optimizer: str = "SGD"
    lr0: float = 0.01
    dataset_path: Optional[str] = None
    dataset_size: Optional[int] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TrainingMetricResponse(BaseModel):
    """训练指标响应"""
    id: int
    task_id: int
    epoch: int
    box_loss: Optional[float] = None
    cls_loss: Optional[float] = None
    dfl_loss: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    map50: Optional[float] = None
    map50_95: Optional[float] = None
    lr: Optional[float] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DatasetValidateRequest(BaseModel):
    """数据集验证请求"""
    images_dir: str
    labels_dir: str
    class_names: list[str]


class DatasetSplitRequest(BaseModel):
    """数据集划分请求"""
    images_dir: str
    labels_dir: str
    output_dir: str
    train_ratio: float = 0.8
    val_ratio: float = 0.1
    test_ratio: float = 0.1


class DataYamlGenerateRequest(BaseModel):
    """data.yaml 生成请求"""
    output_path: str
    class_names: list[str]
    dataset_dir: str


class ModelUploadRequest(BaseModel):
    """手动上传模型版本"""
    model_id: int
    version: str
    description: str = ""
    is_default: bool = True


class ModelValidateRequest(BaseModel):
    """模型评估请求"""
    data_yaml: Optional[str] = None
    img_size: int = 640
    batch_size: int = 16


# ══════════════════════════════════════════════════════════════
# 四、模型管理模块
# ══════════════════════════════════════════════════════════════


class ModelCreate(BaseModel):
    """创建模型"""
    name: str = Field(..., min_length=2, max_length=100, description="模型名称")
    description: str = ""
    base_architecture: str = "yolo26n"
    category: str = "general"
    class_names: list[str] = Field(..., description="类别列表")
    class_names_cn: Optional[dict] = Field(None, description="类别中文名映射")


class ModelUpdate(BaseModel):
    """更新模型（所有字段可选）"""
    name: Optional[str] = None
    description: Optional[str] = None
    base_architecture: Optional[str] = None
    category: Optional[str] = None
    class_names: Optional[list] = None
    class_names_cn: Optional[dict] = None
    status: Optional[str] = None


class ModelResponse(BaseModel):
    """模型响应"""
    id: int
    name: str
    description: Optional[str] = None
    base_architecture: str = "yolo26n"
    category: str
    class_names: list[str]
    class_names_cn: Optional[dict] = None
    status: str = "active"
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ModelVersionResponse(BaseModel):
    """模型版本响应"""
    id: int
    model_id: int
    training_task_id: Optional[int] = None
    version: str
    source: str = "training"
    status: str = "active"
    model_path: Optional[str] = None
    minio_url: Optional[str] = None
    map50: Optional[float] = None
    map50_95: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    per_class_ap: Optional[dict] = None
    description: Optional[str] = None
    file_size: Optional[int] = None
    is_default: bool = False
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SceneModelBindRequest(BaseModel):
    """场景-模型绑定请求"""
    model_id: int
    is_default: bool = False


# ══════════════════════════════════════════════════════════════
# 五、对话模块
# ══════════════════════════════════════════════════════════════


class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    title: Optional[str] = None


class SendMessageRequest(BaseModel):
    """发送消息请求"""
    message: str


class ChatSessionResponse(BaseModel):
    """对话会话响应"""
    id: int
    user_id: int
    session_uuid: str
    title: Optional[str] = None
    status: str = "active"
    message_count: int = 0
    last_message_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ChatMessageResponse(BaseModel):
    """对话消息响应"""
    id: int
    session_id: int
    role: str
    content: str
    agent_used: Optional[str] = None
    tool_calls: Optional[list] = None
    tool_result: Optional[str] = None
    tokens_used: Optional[int] = None
    latency_ms: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════
# 六、知识库模块
# ══════════════════════════════════════════════════════════════


class KnowledgeSearchRequest(BaseModel):
    """知识库检索请求"""
    query: str
    k: int = 5


class KnowledgeSearchResult(BaseModel):
    """知识库检索结果"""
    content: str
    metadata: Optional[dict] = None
    score: float


class KnowledgeStatsResponse(BaseModel):
    """知识库统计响应"""
    total_chunks: int = 0
    sources: list = []


class DeleteDocumentRequest(BaseModel):
    """删除文档请求"""
    source: str


# ══════════════════════════════════════════════════════════════
# 七、通用模型
# ══════════════════════════════════════════════════════════════


class ApiResponse(BaseModel):
    """统一 API 响应"""

    code: int = 200
    message: str = "success"
    data: Optional[Union[dict, list]] = None


class PageParams(BaseModel):
    """分页查询参数"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


class PageResponse(BaseModel):
    """分页响应"""

    total: int
    page: int
    page_size: int
    total_pages: int
    items: list


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str = "healthy"
    app_name: str
    version: str
    database: Optional[str] = None
    redis: Optional[str] = None
    minio: Optional[str] = None
