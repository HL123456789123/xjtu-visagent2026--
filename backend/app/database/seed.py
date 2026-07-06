# -*- coding: utf-8 -*-
"""
数据库种子数据模块
在应用启动时自动检查并创建默认数据（检测场景等）
"""

from app.core.logger import get_logger

logger = get_logger("seed")


# ── 默认角色和权限 ──────────────────────────────────────

DEFAULT_ROLES = [
    {
        "name": "admin",
        "display_name": "管理员",
        "description": "系统管理员，拥有所有权限",
        "is_system": True,
    },
    {
        "name": "operator",
        "display_name": "操作员",
        "description": "操作员，可执行检测、训练、模型管理",
        "is_system": True,
    },
    {
        "name": "viewer",
        "display_name": "访客",
        "description": "只读用户，仅可查看",
        "is_system": True,
    },
]

DEFAULT_PERMISSIONS = [
    # 检测模块
    {"code": "detection:task:create", "name": "创建检测任务", "module": "detection"},
    {"code": "detection:task:view", "name": "查看检测任务", "module": "detection"},
    {"code": "detection:scene:create", "name": "创建检测场景", "module": "detection"},
    {"code": "detection:scene:manage", "name": "管理检测场景", "module": "detection"},
    # 训练模块
    {"code": "training:task:create", "name": "创建训练任务", "module": "training"},
    {"code": "training:task:manage", "name": "管理训练任务", "module": "training"},
    {"code": "training:task:view", "name": "查看训练任务", "module": "training"},
    # 模型模块
    {"code": "model:create", "name": "创建模型", "module": "model"},
    {"code": "model:update", "name": "更新模型", "module": "model"},
    {"code": "model:delete", "name": "删除模型", "module": "model"},
    {"code": "model:view", "name": "查看模型", "module": "model"},
    # 智能体模块
    {"code": "agent:chat", "name": "智能对话", "module": "agent"},
    # 知识库模块
    {"code": "knowledge:manage", "name": "管理知识库", "module": "knowledge"},
    {"code": "knowledge:search", "name": "检索知识库", "module": "knowledge"},
    # 系统模块
    {"code": "system:dashboard", "name": "查看仪表盘", "module": "system"},
    {"code": "system:admin", "name": "系统管理", "module": "system"},
]

# operator 角色拥有的权限
OPERATOR_PERMISSIONS = [
    "detection:task:create",
    "detection:task:view",
    "detection:scene:create",
    "training:task:create",
    "training:task:manage",
    "training:task:view",
    "model:create",
    "model:update",
    "model:view",
    "agent:chat",
    "knowledge:manage",
    "knowledge:search",
    "system:dashboard",
]

# viewer 角色拥有的权限（只读，不含创建/修改资源权限）
VIEWER_PERMISSIONS = [
    "detection:task:view",
    "training:task:view",
    "model:view",
    "agent:chat",
    "knowledge:search",
    "system:dashboard",
]


DEFAULT_SCENES = [
    {
        "name": "coco",
        "display_name": "COCO 通用目标检测",
        "description": "基于 COCO 数据集的 80 类通用目标检测，涵盖人、车辆、动物、家具等常见物体",
        "category": "common",
        "class_names": [
            "person",
            "bicycle",
            "car",
            "motorcycle",
            "airplane",
            "bus",
            "train",
            "truck",
            "boat",
            "traffic light",
            "fire hydrant",
            "stop sign",
            "parking meter",
            "bench",
            "bird",
            "cat",
            "dog",
            "horse",
            "sheep",
            "cow",
            "elephant",
            "bear",
            "zebra",
            "giraffe",
            "backpack",
            "umbrella",
            "handbag",
            "tie",
            "suitcase",
            "frisbee",
            "skis",
            "snowboard",
            "sports ball",
            "kite",
            "baseball bat",
            "baseball glove",
            "skateboard",
            "surfboard",
            "tennis racket",
            "bottle",
            "wine glass",
            "cup",
            "fork",
            "knife",
            "spoon",
            "bowl",
            "banana",
            "apple",
            "sandwich",
            "orange",
            "broccoli",
            "carrot",
            "hot dog",
            "pizza",
            "donut",
            "cake",
            "chair",
            "couch",
            "potted plant",
            "bed",
            "dining table",
            "toilet",
            "tv",
            "laptop",
            "mouse",
            "remote",
            "keyboard",
            "cell phone",
            "microwave",
            "oven",
            "toaster",
            "sink",
            "refrigerator",
            "book",
            "clock",
            "vase",
            "scissors",
            "teddy bear",
            "hair drier",
            "toothbrush",
        ],
        "class_names_cn": {
            "person": "人",
            "bicycle": "自行车",
            "car": "汽车",
            "motorcycle": "摩托车",
            "airplane": "飞机",
            "bus": "公交车",
            "train": "火车",
            "truck": "卡车",
            "boat": "船",
            "traffic light": "红绿灯",
            "fire hydrant": "消防栓",
            "stop sign": "停止标志",
            "parking meter": "停车计时器",
            "bench": "长椅",
            "bird": "鸟",
            "cat": "猫",
            "dog": "狗",
            "horse": "马",
            "sheep": "羊",
            "cow": "牛",
            "elephant": "大象",
            "bear": "熊",
            "zebra": "斑马",
            "giraffe": "长颈鹿",
            "backpack": "背包",
            "umbrella": "雨伞",
            "handbag": "手提包",
            "tie": "领带",
            "suitcase": "行李箱",
            "frisbee": "飞盘",
            "skis": "滑雪板",
            "snowboard": "滑雪板",
            "sports ball": "运动球",
            "kite": "风筝",
            "baseball bat": "棒球棒",
            "baseball glove": "棒球手套",
            "skateboard": "滑板",
            "surfboard": "冲浪板",
            "tennis racket": "网球拍",
            "bottle": "瓶子",
            "wine glass": "酒杯",
            "cup": "杯子",
            "fork": "叉子",
            "knife": "刀",
            "spoon": "勺子",
            "bowl": "碗",
            "banana": "香蕉",
            "apple": "苹果",
            "sandwich": "三明治",
            "orange": "橙子",
            "broccoli": "西兰花",
            "carrot": "胡萝卜",
            "hot dog": "热狗",
            "pizza": "披萨",
            "donut": "甜甜圈",
            "cake": "蛋糕",
            "chair": "椅子",
            "couch": "沙发",
            "potted plant": "盆栽",
            "bed": "床",
            "dining table": "餐桌",
            "toilet": "马桶",
            "tv": "电视",
            "laptop": "笔记本",
            "mouse": "鼠标",
            "remote": "遥控器",
            "keyboard": "键盘",
            "cell phone": "手机",
            "microwave": "微波炉",
            "oven": "烤箱",
            "toaster": "烤面包机",
            "sink": "水槽",
            "refrigerator": "冰箱",
            "book": "书",
            "clock": "时钟",
            "vase": "花瓶",
            "scissors": "剪刀",
            "teddy bear": "泰迪熊",
            "hair drier": "吹风机",
            "toothbrush": "牙刷",
        },
    },
    {
        "name": "remote_sensing",
        "display_name": "遥感目标检测",
        "description": "遥感图像中的目标检测，包括飞机、船舶、储油罐、车辆等",
        "category": "remote_sensing",
        "class_names": [
            "airplane",
            "ship",
            "storage-tank",
            "baseball-diamond",
            "tennis-court",
            "basketball-court",
            "ground-track-field",
            "harbor",
            "bridge",
            "vehicle",
        ],
        "class_names_cn": {
            "airplane": "飞机",
            "ship": "船舶",
            "storage-tank": "储油罐",
            "baseball-diamond": "棒球场",
            "tennis-court": "网球场",
            "basketball-court": "篮球场",
            "ground-track-field": "田径场",
            "harbor": "港口",
            "bridge": "桥梁",
            "vehicle": "车辆",
        },
    },
    {
        "name": "traffic",
        "display_name": "交通场景检测",
        "description": "交通场景中的车辆、行人、交通标志等目标检测",
        "category": "traffic",
        "class_names": [
            "car",
            "bus",
            "truck",
            "motorcycle",
            "bicycle",
            "person",
            "traffic light",
            "traffic sign",
            "stop sign",
            "parking meter",
        ],
        "class_names_cn": {
            "car": "汽车",
            "bus": "公交车",
            "truck": "卡车",
            "motorcycle": "摩托车",
            "bicycle": "自行车",
            "person": "行人",
            "traffic light": "红绿灯",
            "traffic sign": "交通标志",
            "stop sign": "停止标志",
            "parking meter": "停车计时器",
        },
    },
    {
        "name": "agriculture",
        "display_name": "农业病害检测",
        "description": "农作物病虫害检测，适用于农田、果园等场景",
        "category": "agriculture",
        "class_names": [
            "healthy",
            "leaf-blight",
            "rust",
            "mildew",
            "scab",
            "insect-damage",
            "nutrient-deficiency",
        ],
        "class_names_cn": {
            "healthy": "健康",
            "leaf-blight": "叶枯病",
            "rust": "锈病",
            "mildew": "霉病",
            "scab": "疮痂病",
            "insect-damage": "虫害",
            "nutrient-deficiency": "营养缺乏",
        },
    },
]


def seed_scenes(db_session) -> int:
    """
    初始化默认检测场景、角色和权限（如果表为空）

    在应用启动时调用，确保新安装的系统至少有基本场景、模型和 RBAC 权限可用。
    已存在时不会重复创建。

    Args:
        db_session: SQLAlchemy Session

    Returns:
        本次新创建的场景数量
    """
    from app.entity.db_models import (
        DetectionScene,
        Model,
        SceneModel,
        Role,
        Permission,
        RolePermission,
    )

    # ── 初始化角色和权限 ─────────────────────────────
    existing_perms = db_session.query(Permission).count()
    if existing_perms == 0:
        # 创建权限
        perm_objects = {}
        for p in DEFAULT_PERMISSIONS:
            perm = Permission(**p)
            db_session.add(perm)
            db_session.flush()
            perm_objects[p["code"]] = perm
        logger.info(f"创建 {len(DEFAULT_PERMISSIONS)} 个默认权限")

        # 创建角色
        for role_data in DEFAULT_ROLES:
            role = Role(**role_data)
            db_session.add(role)
            db_session.flush()

            # admin 拥有所有权限
            if role.name == "admin":
                for perm in perm_objects.values():
                    db_session.add(RolePermission(role_id=role.id, permission_id=perm.id))
            elif role.name == "operator":
                for code in OPERATOR_PERMISSIONS:
                    if code in perm_objects:
                        db_session.add(
                            RolePermission(role_id=role.id, permission_id=perm_objects[code].id)
                        )
            elif role.name == "viewer":
                for code in VIEWER_PERMISSIONS:
                    if code in perm_objects:
                        db_session.add(
                            RolePermission(role_id=role.id, permission_id=perm_objects[code].id)
                        )

        db_session.commit()
        logger.info("默认角色和权限初始化完成")

    # ── 初始化检测场景和模型 ───────────────────────────
    existing_count = db_session.query(DetectionScene).count()
    if existing_count > 0:
        logger.info(f"检测场景已存在 {existing_count} 个，跳过种子数据初始化")
        return 0

    created = 0
    for scene_data in DEFAULT_SCENES:
        scene = DetectionScene(
            name=scene_data["name"],
            display_name=scene_data["display_name"],
            description=scene_data["description"],
            category=scene_data["category"],
            class_names=scene_data["class_names"],
            class_names_cn=scene_data["class_names_cn"],
            is_active=True,
        )
        db_session.add(scene)
        db_session.flush()  # 获取 scene.id
        created += 1
        logger.info(f"创建默认检测场景: {scene_data['display_name']}")

        # 为每个场景创建一个默认模型
        model_name = f"{scene_data['display_name']}模型"
        model = Model(
            name=model_name,
            description=f"{scene_data['description']}（默认模型）",
            base_architecture="yolov11n",
            category=scene_data["category"],
            class_names=scene_data["class_names"],
            class_names_cn=scene_data["class_names_cn"],
            status="active",
        )
        db_session.add(model)
        db_session.flush()  # 获取 model.id
        logger.info(f"创建默认模型: {model_name}")

        # 创建场景-模型关联
        scene_model = SceneModel(
            scene_id=scene.id,
            model_id=model.id,
            is_default=True,
        )
        db_session.add(scene_model)

    db_session.commit()
    logger.info(f"种子数据初始化完成，共创建 {created} 个检测场景和对应模型")
    return created
