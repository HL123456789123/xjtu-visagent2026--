"""
食物识别端到端手动测试脚本（多图版）
====================================
模拟前端调用真实后端 API（Docker 环境），完整走一遍：
  登录 → 上传多张图片 → 查看识别结果 → 下载原图 → 确认食材 → 查看数据库

前提条件：
  1. Docker 已启动：docker-compose up -d
  2. 后端健康：curl http://localhost:8888/api/health
  3. 准备一张或多张 JPG / PNG 图片

用法：
  cd backend
  python tests/test_food_real_api.py 图片1.jpg 图片2.png
  python tests/test_food_real_api.py *.jpg --username testuser --password 123456
"""

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

# ── 配置 ──────────────────────────────────────────
BASE_URL = "http://localhost:8888"
DEFAULT_USERNAME = "food_tester"
DEFAULT_PASSWORD = "test123456"
DEFAULT_EMAIL = "food_tester@example.com"


def print_step(step: int, title: str):
    """打印步骤标题"""
    print(f"\n{'='*60}")
    print(f"  步骤 {step}: {title}")
    print(f"{'='*60}")


def print_json(data, title: str = ""):
    """美化打印 JSON"""
    if title:
        print(f"\n  [{title}]")
    print(json.dumps(data, indent=2, ensure_ascii=False))


def check_server(client: httpx.Client) -> bool:
    """检查后端服务是否在线"""
    try:
        resp = client.get(f"{BASE_URL}/api/health", timeout=5)
        return resp.status_code == 200
    except httpx.ConnectError:
        return False


def ensure_user(client: httpx.Client, username: str, password: str, email: str) -> dict:
    """确保用户存在：先尝试登录，失败则注册再登录"""
    # 尝试登录
    print(f"\n  尝试登录用户: {username}")
    resp = client.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password},
    )
    if resp.status_code == 200:
        print(f"  ✅ 登录成功！")
        return resp.json()

    # 登录失败，尝试注册
    print(f"  登录失败（用户不存在），尝试注册...")
    resp = client.post(
        f"{BASE_URL}/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
        },
    )
    if resp.status_code == 201:
        print(f"  ✅ 注册成功！")
    else:
        print(f"  ❌ 注册失败: {resp.status_code} {resp.text}")
        sys.exit(1)

    # 注册后再登录
    resp = client.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password},
    )
    if resp.status_code != 200:
        print(f"  ❌ 注册后登录失败: {resp.status_code}")
        sys.exit(1)
    print(f"  ✅ 登录成功！")
    return resp.json()


def upload_and_recognize(client: httpx.Client, image_paths: list[str], conf: float) -> dict:
    """上传多张图片并识别"""
    validated: list[Path] = []
    for p in image_paths:
        path = Path(p)
        if not path.is_file():
            print(f"  ❌ 图片不存在: {p}")
            sys.exit(1)
        validated.append(path)

    total_kb = sum(p.stat().st_size for p in validated) / 1024
    print(f"\n  共 {len(validated)} 张图片（总计 {total_kb:.1f} KB）:")
    for i, p in enumerate(validated):
        size_kb = p.stat().st_size / 1024
        print(f"    [{i}] {p.resolve()}  ({size_kb:.1f} KB)")
    print(f"  置信度阈值: {conf}")

    # 构造多图上传的 files 列表。
    # 注意：
    # 1. FastAPI 0.139+ 要求 multipart 中必须包含 "image" 字段（即使声明了 default=None），
    #    因此将第一张图同时作为 "image" 发送以满足验证。
    # 2. 路由处理逻辑为 images or ([image] if image else [])，
    #    当 images 存在时优先使用 images，image 字段被忽略，不会导致重复处理。
    # 3. conf_threshold 放入 files 列表（filename=None 表示普通表单字段），
    #    避免 httpx 同时使用 data + files 时 multipart 编码兼容问题。
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
    files: list[tuple] = [("conf_threshold", (None, str(conf)))]
    for i, path in enumerate(validated):
        content_type = mime_map.get(path.suffix.lower(), "image/jpeg")
        file_bytes = path.read_bytes()
        # 第一张图同时作为 "image"（满足 FastAPI 验证）和 "images"（实际处理）
        if i == 0:
            files.append(("image", (path.name, file_bytes, content_type)))
        files.append(("images", (path.name, file_bytes, content_type)))

    resp = client.post(
        f"{BASE_URL}/api/food/recognitions",
        files=files,
    )

    if resp.status_code != 201:
        print(f"  ❌ 识别失败: {resp.status_code}")
        print_json(resp.json(), "错误信息")
        sys.exit(1)

    result = resp.json()
    print(f"  ✅ 识别成功！HTTP {resp.status_code}")
    return result


def get_recognition(client: httpx.Client, recognition_id: int) -> dict:
    """查询识别记录"""
    resp = client.get(f"{BASE_URL}/api/food/recognitions/{recognition_id}")
    if resp.status_code != 200:
        print(f"  ❌ 查询失败: {resp.status_code}")
        sys.exit(1)
    print(f"  ✅ 查询成功！")
    return resp.json()


def download_image(client: httpx.Client, recognition_id: int, save_dir: str, image_index: int = 0) -> str:
    """下载识别的原图（默认下载第一张，即 index=0）"""
    resp = client.get(f"{BASE_URL}/api/files/food/{recognition_id}")
    if resp.status_code != 200:
        print(f"  ❌ 下载图片失败: {resp.status_code}")
        return ""

    save_path = Path(save_dir) / f"recognition_{recognition_id}_img{image_index}.jpg"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(resp.content)
    print(f"  ✅ 图片 [{image_index}] 已保存到: {save_path.resolve()}")
    return str(save_path)


def confirm_ingredients(client: httpx.Client, recognition_id: int, result: dict) -> dict:
    """基于识别结果确认食材"""
    # 从识别结果中提取候选食材，转为确认格式
    ingredients = []
    for item in result.get("data", {}).get("ingredients", []):
        ingredients.append({
            "name": item["display_name"],
            "class_name": item["class_name"],
            "quantity": 1,
            "unit": "份",
            "source": item["source"],
        })

    if not ingredients:
        # 模型没识别出东西，手动加一个测试食材
        print("  ⚠️  模型没有识别出食材，使用手动添加的测试食材")
        ingredients = [
            {"name": "番茄", "class_name": "tomato", "quantity": 2, "unit": "个", "source": "manual"}
        ]

    resp = client.put(
        f"{BASE_URL}/api/food/recognitions/{recognition_id}/ingredients",
        json={"ingredients": ingredients},
    )
    if resp.status_code != 200:
        print(f"  ❌ 确认食材失败: {resp.status_code}")
        print_json(resp.json(), "错误信息")
        sys.exit(1)

    print(f"  ✅ 食材已确认！")
    return resp.json()


def print_db_hints():
    """打印数据库查询提示"""
    print(f"""
{'='*60}
  🔍 如何查看数据库中的数据
{'='*60}

  方法1: 通过 Docker 进入 PostgreSQL 命令行
  ────────────────────────────────────────
  docker exec -it visagent-postgres psql -U visagent -d visagent

  然后执行以下 SQL：

  -- 查看所有识别记录
  SELECT id, user_id, status, provider, model_version,
         image_object_name, created_at
  FROM food_recognition_tasks
  ORDER BY id DESC;

  -- 查看某条记录的原始检测结果（JSON）
  SELECT id, raw_detections
  FROM food_recognition_tasks
  WHERE id = <识别ID>;

  -- 查看确认后的食材（JSON）
  SELECT id, confirmed_ingredients, updated_at
  FROM food_recognition_tasks
  WHERE id = <识别ID>;

  -- 查看所有用户
  SELECT id, username, email FROM users;

  方法2: 一行命令直接查
  ────────────────────────────────────────
  docker exec -it visagent-postgres psql -U visagent -d visagent \\
    -c "SELECT id, status, provider, image_object_name, created_at FROM food_recognition_tasks ORDER BY id DESC;"

  方法3: 查看 MinIO 中存储的图片
  ────────────────────────────────────────
  浏览器打开: http://localhost:9001
  登录: minioadmin / minioadmin
  找到 bucket: visagent-images
  路径: food/<用户ID>/年/月/日/xxx.jpg

{'='*60}""")


def main():
    parser = argparse.ArgumentParser(description="食物识别端到端测试（真实 Docker 环境，支持多图）")
    parser.add_argument("images", nargs="+", help="图片文件路径（JPG/PNG），可传多个")
    parser.add_argument("--username", default=DEFAULT_USERNAME, help=f"用户名（默认: {DEFAULT_USERNAME}）")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help=f"密码（默认: {DEFAULT_PASSWORD}）")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help=f"邮箱（默认: {DEFAULT_EMAIL}）")
    parser.add_argument("--conf", type=float, default=0.25, help="置信度阈值（默认: 0.25）")
    parser.add_argument("--save-dir", default="./test_output", help="结果保存目录（默认: ./test_output）")
    args = parser.parse_args()

    image_names = ", ".join(Path(p).name for p in args.images)
    print(f"""
╔══════════════════════════════════════════════════════════╗
║          🍳 食物识别端到端测试（真实环境·多图）           ║
╠══════════════════════════════════════════════════════════╣
║  后端地址: {BASE_URL:<43s} ║
║  用户:     {args.username:<43s} ║
║  图片数:   {len(args.images):<43d} ║
║  图片:     {image_names[:43]:<43s} ║
╚══════════════════════════════════════════════════════════╝""")

    # 创建 HTTP 客户端（自动携带 cookie，禁用系统代理避免冲突）
    with httpx.Client(timeout=30, trust_env=False) as client:

        # ── 步骤 0: 检查服务 ─────────────────────────
        print_step(0, "检查后端服务是否在线")
        if not check_server(client):
            print(f"  ❌ 无法连接到 {BASE_URL}")
            print(f"  请确认 Docker 已启动: docker-compose up -d")
            sys.exit(1)
        print(f"  ✅ 后端服务正常运行")

        # ── 步骤 1: 登录/注册 ────────────────────────
        print_step(1, "用户认证")
        user_data = ensure_user(client, args.username, args.password, args.email)
        user_id = user_data.get("user", {}).get("id")
        print(f"  用户 ID: {user_id}")
        print(f"  用户名: {user_data.get('user', {}).get('username')}")

        # ── 步骤 2: 上传多张图片并识别 ───────────────
        print_step(2, "上传多张图片 → AI 识别")
        start_time = time.time()
        result = upload_and_recognize(client, args.images, args.conf)
        elapsed = time.time() - start_time
        recognition_id = result["data"]["recognition_id"]

        print_json(result["data"], "识别结果")
        print(f"\n  ⏱️  耗时: {elapsed:.2f} 秒")
        print(f"  📋 识别 ID: {recognition_id}")
        print(f"  📸 上传图片数: {len(args.images)}")
        print(f"  🔍 识别到 {len(result['data']['ingredients'])} 种食材:")
        for item in result["data"]["ingredients"]:
            print(f"     - {item['display_name']} ({item['class_name']}) "
                  f"置信度: {item['confidence']:.1%} "
                  f"位置: [{item['bbox']['x1']:.0f}, {item['bbox']['y1']:.0f}, "
                  f"{item['bbox']['x2']:.0f}, {item['bbox']['y2']:.0f}]")

        # ── 步骤 3: 查询识别记录 ─────────────────────
        print_step(3, "查询识别记录详情")
        detail = get_recognition(client, recognition_id)
        confirmed = detail["data"]["confirmed_ingredients"]
        print(f"  已确认食材数量: {len(confirmed)}（预期: 0，还没确认）")

        # ── 步骤 4: 下载原图（第一张） ───────────────
        print_step(4, "从 MinIO 下载原图（第一张）")
        saved_path = download_image(client, recognition_id, args.save_dir, image_index=0)
        if saved_path:
            original_size = Path(args.images[0]).stat().st_size
            downloaded_size = Path(saved_path).stat().st_size
            print(f"  原图大小: {original_size} bytes")
            print(f"  下载大小: {downloaded_size} bytes")
            print(f"  内容一致: {'✅' if original_size == downloaded_size else '❌'}")

        # ── 步骤 5: 确认食材 ─────────────────────────
        print_step(5, "确认食材（存入数据库）")
        confirm_result = confirm_ingredients(client, recognition_id, result)
        print_json(confirm_result["data"], "确认后的食材")

        # ── 步骤 6: 再次查询验证 ─────────────────────
        print_step(6, "再次查询，验证食材已持久化")
        detail2 = get_recognition(client, recognition_id)
        confirmed2 = detail2["data"]["confirmed_ingredients"]
        print(f"  已确认食材数量: {len(confirmed2)}")
        for item in confirmed2:
            print(f"     - {item['name']} × {item['quantity']}{item['unit']} "
                  f"(来源: {item['source']})")

        # ── 汇总 ─────────────────────────────────────
        print(f"""
{'='*60}
  ✅ 全部完成！汇总
{'='*60}

  用户 ID:       {user_id}
  识别 ID:       {recognition_id}
  上传图片数:    {len(args.images)}
  图片列表:      {[Path(p).name for p in args.images]}
  识别食材:      {[i['display_name'] for i in result['data']['ingredients']]}
  确认食材:      {[i['name'] for i in confirmed2]}
  图片存储路径:  {result['data']['image_url']}
  下载的图片:    {saved_path or '无'}
  Provider:      {result['data']['provider']}
  模型版本:      {result['data']['model_version']}
""")

        # ── 数据库查看提示 ───────────────────────────
        print_db_hints()


if __name__ == "__main__":
    main()
