"""
Pydantic Schema 模型测试：请求验证、序列化、约束
"""
import pytest
from pydantic import ValidationError
from datetime import datetime
from app.core.tz import now_cst
from app.entity.recipe_schema import GeneratorInfo, RecipeResponse, RecipePreferences, Ingredient, NutritionInfo, RecipeStep
from app.entity.schemas import (
    UserRegister, UserLogin, TokenResponse, UserResponse, UserBrief,
    UserUpdate, ChangePassword, RoleResponse, RoleCreate,
    PermissionResponse, ApiResponse, PageParams, PageResponse,
)


class TestUserRegister:
    """用户注册 Schema 验证"""

    def test_valid_register(self):
        """有效注册数据"""
        data = UserRegister(
            username="testuser",
            email="test@example.com",
            password="password123",
        )
        assert data.username == "testuser"
        assert data.email == "test@example.com"
        assert data.password == "password123"

    def test_username_too_short(self):
        """用户名过短（< 3）"""
        with pytest.raises(ValidationError):
            UserRegister(username="ab", email="test@example.com", password="password123")

    def test_username_too_long(self):
        """用户名过长（> 50）"""
        with pytest.raises(ValidationError):
            UserRegister(
                username="a" * 51,
                email="test@example.com",
                password="password123",
            )

    def test_password_too_short(self):
        """密码过短（< 6）"""
        with pytest.raises(ValidationError):
            UserRegister(username="testuser", email="test@example.com", password="12345")

    def test_missing_username(self):
        """缺少用户名"""
        with pytest.raises(ValidationError):
            UserRegister(email="test@example.com", password="password123")

    def test_missing_email(self):
        """缺少邮箱"""
        with pytest.raises(ValidationError):
            UserRegister(username="testuser", password="password123")

    def test_missing_password(self):
        """缺少密码"""
        with pytest.raises(ValidationError):
            UserRegister(username="testuser", email="test@example.com")


class TestUserLogin:
    """用户登录 Schema 验证"""

    def test_valid_login(self):
        """有效登录数据"""
        data = UserLogin(username="testuser", password="password123")
        assert data.username == "testuser"
        assert data.password == "password123"

    def test_missing_username(self):
        """缺少用户名"""
        with pytest.raises(ValidationError):
            UserLogin(password="password123")

    def test_missing_password(self):
        """缺少密码"""
        with pytest.raises(ValidationError):
            UserLogin(username="testuser")


class TestUserResponse:
    """用户响应 Schema 序列化"""

    def test_user_response_from_attributes(self):
        """从 ORM 对象属性创建"""
        data = UserResponse(
            id=1,
            username="testuser",
            email="test@example.com",
            is_active=True,
            roles=[],
            created_at=now_cst(),
        )
        assert data.id == 1
        assert data.is_active is True

    def test_user_brief_from_attributes(self):
        """UserBrief 从属性创建"""
        data = UserBrief(
            id=1,
            username="testuser",
            email="test@example.com",
            roles=["admin"],
        )
        assert data.id == 1
        assert "admin" in data.roles


class TestTokenResponse:
    """Token 响应 Schema"""

    def test_token_response(self):
        """Token 响应结构"""
        user_brief = UserBrief(
            id=1, username="test", email="test@example.com", roles=[]
        )
        data = TokenResponse(
            access_token="eyJhbGciOi...",
            token_type="bearer",
            user=user_brief,
        )
        assert data.access_token == "eyJhbGciOi..."
        assert data.token_type == "bearer"
        assert data.user.username == "test"


class TestChangePassword:
    """修改密码 Schema"""

    def test_valid_change_password(self):
        """有效密码修改"""
        data = ChangePassword(old_password="old123", new_password="new456")
        assert data.old_password == "old123"
        assert data.new_password == "new456"

    def test_new_password_too_short(self):
        """新密码过短"""
        with pytest.raises(ValidationError):
            ChangePassword(old_password="old123", new_password="12345")


class TestRoleSchema:
    """角色权限 Schema"""

    def test_role_create(self):
        """创建角色"""
        data = RoleCreate(
            name="operator",
            display_name="操作员",
            description="日常操作人员",
            permission_codes=["detection:task:create", "detection:task:read"],
        )
        assert data.name == "operator"
        assert len(data.permission_codes) == 2

    def test_role_response(self):
        """角色响应"""
        data = RoleResponse(
            id=1,
            name="admin",
            display_name="管理员",
            is_system=True,
            permissions=["detection:task:create"],
            created_at=now_cst(),
        )
        assert data.is_system is True
        assert "detection:task:create" in data.permissions

    def test_permission_response(self):
        """权限响应"""
        data = PermissionResponse(
            id=1,
            code="detection:task:create",
            name="创建检测任务",
            module="detection",
        )
        assert data.module == "detection"


class TestPageParams:
    """分页参数 Schema"""

    def test_default_values(self):
        """默认值"""
        params = PageParams()
        assert params.page == 1
        assert params.page_size == 20

    def test_page_too_small(self):
        """页码 < 1"""
        with pytest.raises(ValidationError):
            PageParams(page=0)

    def test_page_size_too_large(self):
        """每页数量 > 100"""
        with pytest.raises(ValidationError):
            PageParams(page_size=101)


class TestApiResponse:
    """通用 API 响应"""

    def test_default_response(self):
        """默认响应"""
        resp = ApiResponse()
        assert resp.code == 200
        assert resp.message == "success"
        assert resp.data is None

    def test_custom_response(self):
        """自定义响应"""
        resp = ApiResponse(code=201, message="创建成功", data={"id": 1})
        assert resp.code == 201
        assert resp.message == "创建成功"
        assert resp.data == {"id": 1}


class TestPageResponse:
    """分页响应"""

    def test_page_response(self):
        """分页响应结构"""
        resp = PageResponse(
            total=100,
            page=1,
            page_size=20,
            total_pages=5,
            items=[{"id": 1}, {"id": 2}],
        )
        assert resp.total == 100
        assert resp.total_pages == 5
        assert len(resp.items) == 2
class TestGeneratorInfoSchema:
    """生成器信息 Schema 测试（V1 第七节第1点）"""
    
    def test_valid_generator_info(self):
        """正例：有效生成器信息"""
        gen = GeneratorInfo(
            provider="openai",
            model="gpt-4",
            is_mock=False,
        )
        assert gen.provider == "openai"
        assert gen.is_mock is False
    
    def test_mock_generator(self):
        """正例：Mock 生成器"""
        gen = GeneratorInfo(
            provider="fake",
            model="fixture-v1",
            is_mock=True,
        )
        assert gen.is_mock is True


class TestRecipeResponseSchema:
    """API 响应 Schema 测试（V1 第六节第1点）"""
    
    def test_valid_response(self):
        """正例：有效响应"""
        from datetime import datetime
        response = RecipeResponse(
            recipe_id=1,
            recognition_id=12,
            version=1,
            title="番茄炒蛋",
            summary="一道家常菜",
            servings=2,
            cooking_time_minutes=20,
            difficulty="简单",
            ingredients=[Ingredient(name="番茄", amount=2, unit="个")],
            steps=[RecipeStep(step_no=1, description="番茄切块", duration_minutes=5)],
            nutrition=NutritionInfo(
                basis="per_serving",
                calories_kcal=280,
                protein_g=16.5,
                fat_g=15.2,
                carbohydrates_g=18.4,
            ),
            nutrition_disclaimer="营养数据由模型估算，仅供参考",
            generator=GeneratorInfo(provider="fake", model="fixture-v1", is_mock=True),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert response.recipe_id == 1
        assert response.version == 1
        assert response.nutrition_disclaimer != ""