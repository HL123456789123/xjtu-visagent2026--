# 食物识别菜谱平台：API 与模块接口冻结完整版（V1）

> 本文档是五天开发期间的唯一接口标准。其他计划、个人任务、代码注释或群聊内容与本文冲突时，一律以本文为准。  
> 适用分支：`develop` 及全部个人功能分支。

---

# 一、最终确定的项目实现

## 1. 主流程

```text
登录
→ 上传 1 至多张 JPG/PNG 图片
→ YOLO 检测图片中的多种原材料
→ 返回候选食材
→ 用户增删改并确认食材
→ 后端读取确认后的食材
→ 将食材和偏好填入固定 Prompt
→ 大模型直接生成结构化菜谱
→ 后端校验并保存
→ 前端结构化展示
→ 用户继续提问或要求修改
→ 大模型返回回答或新菜谱
→ 更新菜谱并刷新页面
```

## 2. 智能体采用最小 LangGraph

首次生成：

```text
START
→ load_confirmed_ingredients
→ generate_recipe
→ validate_and_save
→ END
```

对话问答或修改：

```text
START
→ load_recipe_context
→ call_llm
→ 判断 action
   ├─ answer：直接回答
   └─ update_recipe：校验并保存新版本
→ END
```

五天 MVP 不实现复杂 Supervisor、QA Agent、Nutrition Agent 和多工具编排。

## 3. 营养数据

营养估算直接由大模型随菜谱一起输出，并固定显示：

```text
营养数据由模型估算，仅供参考，不构成医疗或营养建议。
```

## 4. 黄小石的模型任务

黄小石在租用的 GPU 服务器训练 YOLO 多类别目标检测模型，只需保证：

```text
固定输入接口
→ 模型推理
→ 固定输出接口
```

她不负责 Food API、数据库和前端。

## 5. 不再安排技术讨论任务

成员不再讨论字段名、接口路径、SSE 事件、Provider 或 Repository。所有人直接按本文实现。

---

# 二、全局统一规则

## 1. API 前缀

```text
/api
```

## 2. 认证

Food、Recipe、Chat 接口都要求登录。后端通过 `current_user` 获取用户身份，客户端不得上传 `user_id`。

## 3. 成功响应

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

创建成功使用 HTTP 201：

```json
{
  "code": 201,
  "message": "created",
  "data": {}
}
```

## 4. 错误响应

```json
{
  "code": 404,
  "message": "识别记录不存在",
  "data": null
}
```

## 5. 时间格式

```text
2026-07-14T21:30:00+08:00
```

## 6. ID 类型

```text
recognition_id
recipe_id
session_id
message_id
```

全部使用整数。

## 7. 图片规则

```text
格式：JPG、JPEG、PNG
最大：10 MB
每次：1 张
```

## 8. 默认值

```text
conf_threshold = 0.25
servings = 2
taste = "家常"
LLM timeout = 60 秒
```

---

# 三、固定字段定义

## 1. BoundingBox

坐标使用原图像素：

```json
{
  "x1": 120.4,
  "y1": 80.2,
  "x2": 310.7,
  "y2": 265.1
}
```

## 2. 模型原始输出 ModelDetection

黄小石的推理代码必须返回：

```json
{
  "class_name": "tomato",
  "confidence": 0.9321,
  "bbox": {
    "x1": 120.4,
    "y1": 80.2,
    "x2": 310.7,
    "y2": 265.1
  }
}
```

模型层不返回中文名，不生成数据库 ID，不访问数据库。

## 3. API 候选食材 IngredientCandidate

后端转换为：

```json
{
  "candidate_id": "det-1",
  "class_name": "tomato",
  "display_name": "番茄",
  "confidence": 0.9321,
  "bbox": {
    "x1": 120.4,
    "y1": 80.2,
    "x2": 310.7,
    "y2": 265.1
  },
  "source": "model"
}
```

`source` 只能是：

```text
model
manual
```

## 4. 用户确认食材 ConfirmedIngredient

```json
{
  "name": "番茄",
  "class_name": "tomato",
  "quantity": 2,
  "unit": "个",
  "source": "model"
}
```

手动添加：

```json
{
  "name": "鸡蛋",
  "class_name": null,
  "quantity": 3,
  "unit": "个",
  "source": "manual"
}
```

## 5. 用户偏好 RecipePreferences

```json
{
  "servings": 2,
  "taste": "家常",
  "max_time_minutes": 30,
  "avoid_ingredients": []
}
```

约束：

```text
servings：1～10
taste：最长 20 字
max_time_minutes：5～180，可为空
avoid_ingredients：字符串数组
```

---

# 四、黄小石与绕家辉的模型接口

## 1. 统一 Python 接口

```python
class FoodRecognitionProvider:
    def recognize(
        self,
        image_path: str,
        conf_threshold: float = 0.25,
    ) -> list[ModelDetection]:
        ...
```

## 2. 输入

```text
image_path：后端准备好的本地图片绝对路径
conf_threshold：0～1，默认 0.25
```

## 3. 输出

```json
[
  {
    "class_name": "tomato",
    "confidence": 0.93,
    "bbox": {
      "x1": 120.4,
      "y1": 80.2,
      "x2": 310.7,
      "y2": 265.1
    }
  },
  {
    "class_name": "egg",
    "confidence": 0.88,
    "bbox": {
      "x1": 350.0,
      "y1": 100.0,
      "x2": 470.0,
      "y2": 230.0
    }
  }
]
```

无结果返回：

```json
[]
```

模型不可用时抛出：

```python
FoodModelUnavailableError
```

Food API 转换为 HTTP 503。

## 4. 类别文件

```text
backend/scripts/food_model/classes.yaml
```

示例：

```yaml
names:
  0:
    class_name: tomato
    display_name: 番茄
  1:
    class_name: egg
    display_name: 鸡蛋
```

黄小石根据样本量和标注质量独立选择最稳定的 12 类，不再组织全员讨论。

## 5. 权重交付

权重不进入 Git。

宿主机：

```text
./models/food/best.pt
```

Docker 容器：

```text
/models/food/best.pt
```

环境变量：

```env
FOOD_PROVIDER=yolo
FOOD_MODEL_PATH=/models/food/best.pt
FOOD_CLASSES_PATH=/app/backend/scripts/food_model/classes.yaml
FOOD_CONF_THRESHOLD=0.25
```

---

# 五、Food API

负责人：绕家辉  
前端调用：刘楚涵

## 1. 创建识别任务并同步返回结果

```http
POST /api/food/recognitions
Content-Type: multipart/form-data
```

表单：

```text
images：必填，1 至多张 JPG/JPEG/PNG 图片
image：兼容字段，可携带第一张图片
conf_threshold：选填，默认 0.25
```

多图识别仍同步返回一个 `recognition_id` 和一组汇总候选食材，不要求前端轮询。单张图片最大 10 MB。

响应：

```json
{
  "code": 201,
  "message": "识别完成",
  "data": {
    "recognition_id": 12,
    "status": "completed",
    "provider": "yolo",
    "model_version": "food-yolo-v1",
    "image_url": "/api/files/food/12",
    "ingredients": [
      {
        "candidate_id": "det-1",
        "class_name": "tomato",
        "display_name": "番茄",
        "confidence": 0.9321,
        "bbox": {
          "x1": 120.4,
          "y1": 80.2,
          "x2": 310.7,
          "y2": 265.1
        },
        "source": "model"
      }
    ],
    "created_at": "2026-07-14T21:30:00+08:00"
  }
}
```

`provider` 只能是：

```text
mock
yolo
```

接口采用同步实现，不要求前端轮询。`image_url` 可指向识别记录或第一张图片资源；多图场景不强制返回逐张图片 URL。

## 2. 查询识别记录

```http
GET /api/food/recognitions/{recognition_id}
```

响应：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "recognition_id": 12,
    "status": "completed",
    "provider": "yolo",
    "model_version": "food-yolo-v1",
    "image_url": "/api/files/food/12",
    "ingredients": [],
    "confirmed_ingredients": [],
    "created_at": "2026-07-14T21:30:00+08:00",
    "updated_at": "2026-07-14T21:35:00+08:00"
  }
}
```

## 3. 确认最终食材

```http
PUT /api/food/recognitions/{recognition_id}/ingredients
Content-Type: application/json
```

请求：

```json
{
  "ingredients": [
    {
      "name": "番茄",
      "class_name": "tomato",
      "quantity": 2,
      "unit": "个",
      "source": "model"
    },
    {
      "name": "鸡蛋",
      "class_name": null,
      "quantity": 3,
      "unit": "个",
      "source": "manual"
    }
  ]
}
```

规则：

```text
至少 1 项
本次数组覆盖旧 confirmed_ingredients
前端不上传 candidate_id
name 不能为空
```

响应：

```json
{
  "code": 200,
  "message": "食材已确认",
  "data": {
    "recognition_id": 12,
    "confirmed_ingredients": [],
    "confirmed_at": "2026-07-14T21:35:00+08:00"
  }
}
```

---

# 六、Recipe API

负责人：陈煜君

## 1. 生成菜谱

```http
POST /api/recipes
Content-Type: application/json
```

请求：

```json
{
  "recognition_id": 12,
  "preferences": {
    "servings": 2,
    "taste": "清淡",
    "max_time_minutes": 30,
    "avoid_ingredients": []
  }
}
```

后端固定执行：

```text
检查 recognition_id 属于当前用户
→ 读取 confirmed_ingredients
→ 未确认则返回 422
→ 构造固定 Prompt
→ 调用大模型
→ 校验结构化 JSON
→ 保存菜谱
→ 返回
```

响应：

```json
{
  "code": 201,
  "message": "菜谱生成成功",
  "data": {
    "recipe_id": 101,
    "recognition_id": 12,
    "version": 1,
    "title": "番茄炒蛋",
    "summary": "一道适合两人食用的家常快手菜。",
    "servings": 2,
    "cooking_time_minutes": 20,
    "difficulty": "简单",
    "ingredients": [
      {
        "name": "番茄",
        "amount": 2,
        "unit": "个",
        "note": null
      }
    ],
    "steps": [
      {
        "step_no": 1,
        "description": "番茄洗净切块。",
        "duration_minutes": 5
      }
    ],
    "nutrition": {
      "basis": "per_serving",
      "calories_kcal": 280,
      "protein_g": 16.5,
      "fat_g": 15.2,
      "carbohydrates_g": 18.4
    },
    "nutrition_disclaimer": "营养数据由模型估算，仅供参考，不构成医疗或营养建议。",
    "generator": {
      "provider": "openai_compatible",
      "model": "configured-model",
      "is_mock": false
    },
    "created_at": "2026-07-14T21:40:00+08:00",
    "updated_at": "2026-07-14T21:40:00+08:00"
  }
}
```

## 2. 查询菜谱

```http
GET /api/recipes/{recipe_id}
```

返回结构与生成接口一致。

## 3. 版本规则

```text
首次生成：version = 1
每次对话修改：version + 1
普通问答：version 不变
```

---

# 七、大模型输入输出

## 1. 配置

使用 OpenAI-compatible 接口：

```env
LLM_MODE=real
LLM_BASE_URL=https://example.com/v1
LLM_API_KEY=replace_me
LLM_MODEL=replace_me
LLM_TIMEOUT_SECONDS=60
```

测试：

```env
LLM_MODE=fake
```

Fake 返回必须标记：

```json
{
  "provider": "fake",
  "model": "fixture-v1",
  "is_mock": true
}
```

真实模式失败时返回 503，不得自动切成 Fake。

## 2. 首次生成 Prompt

系统 Prompt：

```text
你是一名家庭菜谱助手。请根据用户已经确认拥有的食材，生成一道实际可制作的菜谱。

要求：
1. 优先使用用户已有食材。
2. 可以加入少量常见调味料，不得虚构大量主要食材。
3. 遵守份数、口味、时间限制和忌口。
4. 输出菜名、简介、份数、耗时、难度、食材用量、步骤和每份营养估算。
5. 严格输出指定 JSON。
6. 不输出 Markdown、代码块或额外解释。
```

用户 Prompt：

```text
已确认食材：
{confirmed_ingredients_json}

用户偏好：
{preferences_json}

请生成一道菜谱。
```

## 3. LLM 输出

```json
{
  "title": "番茄炒蛋",
  "summary": "一道适合两人食用的家常快手菜。",
  "servings": 2,
  "cooking_time_minutes": 20,
  "difficulty": "简单",
  "ingredients": [
    {
      "name": "番茄",
      "amount": 2,
      "unit": "个",
      "note": null
    }
  ],
  "steps": [
    {
      "step_no": 1,
      "description": "番茄洗净切块。",
      "duration_minutes": 5
    }
  ],
  "nutrition": {
    "basis": "per_serving",
    "calories_kcal": 280,
    "protein_g": 16.5,
    "fat_g": 15.2,
    "carbohydrates_g": 18.4
  }
}
```

`recipe_id`、`version`、时间和 `generator` 由后端补充。

---

# 八、Chat API 与 SSE

## 1. 创建会话

```http
POST /api/chat/sessions
```

请求：

```json
{
  "recipe_id": 101
}
```

响应：

```json
{
  "code": 201,
  "message": "会话创建成功",
  "data": {
    "session_id": 501,
    "recipe_id": 101,
    "created_at": "2026-07-14T21:45:00+08:00"
  }
}
```

## 2. 发送消息

```http
POST /api/chat/sessions/{session_id}/messages
Accept: text/event-stream
```

请求：

```json
{
  "content": "把这道菜改成三人份，并且少放油。"
}
```

## 3. 对话 LLM 输出

普通问答：

```json
{
  "action": "answer",
  "answer": "鸡蛋炒至刚凝固时先盛出，可以避免口感过老。",
  "recipe": null
}
```

修改菜谱：

```json
{
  "action": "update_recipe",
  "answer": "已经调整为三人份，并减少了食用油用量。",
  "recipe": {
    "title": "少油版番茄炒蛋",
    "summary": "适合三人食用的少油版本。",
    "servings": 3,
    "cooking_time_minutes": 20,
    "difficulty": "简单",
    "ingredients": [],
    "steps": [],
    "nutrition": {
      "basis": "per_serving",
      "calories_kcal": 230,
      "protein_g": 15,
      "fat_g": 10,
      "carbohydrates_g": 18
    }
  }
}
```

## 4. SSE 只保留四种事件

```text
token
recipe_updated
done
error
```

不使用：

```text
tool_call
tool_result
```

### token

```text
event: token
data: {"content":"已经调整为三人份，并减少了食用油用量。"}
```

允许一次发送完整回答，不强制逐字流式。

### recipe_updated

```text
event: recipe_updated
data: {"recipe_id":101,"version":2}
```

前端收到后调用：

```http
GET /api/recipes/101
```

### done

```text
event: done
data: {"message_id":9001}
```

### error

```text
event: error
data: {"code":"LLM_UNAVAILABLE","message":"智能服务暂时不可用"}
```

---

# 九、Repository 接口

负责人：绕家辉  
调用者：陈煜君

```python
class FoodRepository:
    def create_recognition(...): ...
    def get_recognition_for_user(recognition_id: int, user_id: int): ...
    def save_raw_detections(recognition_id: int, detections: list[dict]): ...
    def replace_confirmed_ingredients(
        recognition_id: int,
        user_id: int,
        ingredients: list[dict],
    ): ...
    def get_confirmed_ingredients(
        recognition_id: int,
        user_id: int,
    ) -> list[dict]: ...

class RecipeRepository:
    def create_recipe(
        user_id: int,
        recognition_id: int,
        recipe_data: dict,
        generator: dict,
    ): ...
    def get_recipe_for_user(recipe_id: int, user_id: int): ...
    def save_new_recipe_version(
        recipe_id: int,
        user_id: int,
        recipe_data: dict,
    ): ...

class ChatRepository:
    def create_session(user_id: int, recipe_id: int): ...
    def get_session_for_user(session_id: int, user_id: int): ...
    def save_message(session_id: int, role: str, content: str): ...
```

陈煜君不直接写 SQLAlchemy 查询。

---

# 十、数据库决定

## food_recognition_tasks

```text
id
user_id
image_object_name
status
provider
model_version
raw_detections（JSON）
confirmed_ingredients（JSON）
created_at
updated_at
```

## recipes

```text
id
user_id
recognition_id
version
recipe_data（JSON）
generator（JSON）
created_at
updated_at
```

五天 MVP 将完整菜谱保存为 JSON，不拆成多张步骤表。

## chat_sessions

增加：

```text
recipe_id
```

ORM 和 Alembic migration 只由绕家辉修改。

---

# 十一、状态码

| HTTP | 业务错误码 | 场景 |
|---:|---|---|
| 400 | `BAD_REQUEST` | 普通请求错误 |
| 401 | `UNAUTHORIZED` | 未登录 |
| 403 | `FORBIDDEN` | 访问他人资源 |
| 404 | `RECOGNITION_NOT_FOUND` | 识别记录不存在 |
| 404 | `RECIPE_NOT_FOUND` | 菜谱不存在 |
| 404 | `SESSION_NOT_FOUND` | 会话不存在 |
| 413 | `IMAGE_TOO_LARGE` | 图片超过 10 MB |
| 415 | `UNSUPPORTED_IMAGE_TYPE` | 非 JPG/JPEG/PNG |
| 422 | `NO_CONFIRMED_INGREDIENTS` | 未确认食材 |
| 422 | `EMPTY_INGREDIENTS` | 食材为空 |
| 422 | `INVALID_LLM_OUTPUT` | LLM 输出不合格 |
| 503 | `FOOD_MODEL_UNAVAILABLE` | YOLO 不可用 |
| 503 | `LLM_UNAVAILABLE` | 大模型不可用 |
| 500 | `INTERNAL_ERROR` | 未预期错误 |

---

# 十二、固定文件命名

```text
backend/app/api/food.py
backend/app/api/recipes.py
backend/app/api/chat.py

backend/app/entity/food_schemas.py
backend/app/entity/recipe_schemas.py

backend/app/services/food_recognition_service.py
backend/app/services/recipe_service.py
backend/app/services/agent_graph.py
backend/app/services/agent_prompts.py
backend/app/services/chat_service.py

backend/app/repositories/food_repository.py
backend/app/repositories/recipe_repository.py
backend/app/repositories/chat_repository.py

frontend/src/api/food.js
frontend/src/api/recipe.js
frontend/src/api/chat.js

integration/day3-mock
integration/day4-real
```

统一使用 `recipes.py`，不使用 `recipe.py`。

---

# 十三、Canonical Fixture

负责人：吴雯

```text
backend/tests/fixtures/food_recognition_success.json
backend/tests/fixtures/food_recognition_empty.json
backend/tests/fixtures/recipe_success.json
backend/tests/fixtures/sse_recipe_update.txt
```

前端 Mock、后端测试和联调测试共用这一套字段。

---

# 十四、每个人只需执行的接口任务

## 闫灿宇

```text
维护本文
检查 PR 是否遵守本文
统一注册 backend/main.py 路由
统一接前端 router/sidebar
不再组织成员设计字段
```

## 刘楚涵

```text
按 Food API 完成上传、展示和食材确认
确认后保存 recognition_id
不自行改字段
```

## 黄小石

```text
输入严格接收 image_path 和 conf_threshold
输出严格返回 list[ModelDetection]
提交 classes.yaml、训练脚本和使用说明
best.pt 不进 Git
```

## 绕家辉

```text
实现 Food API
实现 Provider 适配
实现 ORM、migration 和 Repository
把模型输出转换成 IngredientCandidate
```

## 陈煜君

```text
读取 confirmed_ingredients
按固定 Prompt 调用大模型
校验并保存菜谱
实现最小 LangGraph、Recipe API 和 Chat SSE
不实现复杂多智能体
```

## 李晨宁

```text
按固定 Recipe JSON 展示
只解析 token、recipe_updated、done、error
收到 recipe_updated 后重新 GET
```

## 吴雯

```text
按本文生成 fixture 和契约测试
接口不一致直接判失败
不写多版本兼容层
```

---

# 十五、计划中的技术讨论任务统一替换

删除或改写：

```text
组织讨论接口
由成员提供接口初稿
中午确认字段
下午冻结事件名
讨论 Provider 和 Repository
考虑采用哪种智能体结构
```

统一改成：

```text
阅读《API 与模块接口冻结完整版（V1）》
按冻结接口建立代码骨架
运行 canonical fixture 契约测试
发现不一致时提交问题，不得自行改字段
```

第 1 天改为：

```text
把本文提交共享仓库
→ 各成员阅读
→ Codex/Qoder 按本文建立 Schema、API 和 Mock
→ 吴雯运行契约检查
→ 闫灿宇确认所有分支使用同一版本
```

---

# 十六、最终验收主流程

```text
1. 登录。
2. 上传 1 至多张 JPG/PNG。
3. 返回多种候选食材。
4. 用户删除误识别项并增加缺失项。
5. 提交最终食材。
6. POST /api/recipes 生成菜谱。
7. 展示结构化菜谱和营养免责声明。
8. 创建聊天会话。
9. 输入“改成三人份并少放油”。
10. SSE 返回 token、recipe_updated、done。
11. 前端重新 GET 菜谱。
12. 展示 version=2 的新菜谱。
13. Docker 环境中再执行一次。
```

---

# 十七、冻结规则

本文为 V1。

只有以下情况允许修改：

```text
现有源码无法实现
严重安全问题
契约测试证明结构存在明确错误
```

修改流程：

```text
提出具体冲突
→ 闫灿宇确认
→ 本文升级版本
→ 吴雯更新 fixture 和测试
→ 受影响成员统一修改
```

禁止：

```text
单个成员为方便而改字段
前后端维护不同命名
长期兼容两套接口
只在群里口头通知变化
```


