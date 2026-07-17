# API V1.1 多图上传迁移说明

## 为什么改成多图

用户可能需要用不同角度或不同容器中的图片补充同一餐的食材。单图接口会迫使用户创建多条识别记录，前端还需要自行合并食材，容易让 `recognition_id`、候选食材和后续 Recipe 输入失去一致性。V1.1 将一次用户操作定义为一个图片批次：每批 1～5 张图片，只创建一个整数 `recognition_id`，最后仍由用户确认一份 `confirmed_ingredients`。

## 旧版和新版差异

| 项目 | V1.0 | V1.1 |
| --- | --- | --- |
| multipart 文件字段 | `image` | 只使用可重复字段 `images` |
| 图片数量 | 每次 1 张 | 每批 1～5 张 |
| 大小限制 | 单张 10 MB | 单张 10 MB，整批 50 MB |
| 识别记录 | 一张图一个 `recognition_id` | 一批图片一个 `recognition_id` |
| 图片响应 | 单个 `image_url` | `images[{image_index,image_url}]` |
| bbox 关联 | 默认属于唯一图片 | 每个候选使用 `image_index` 关联图片 |
| Provider | 单图 `recognize` | 保持单图 `recognize` 不变 |
| Service | 调用一次 Provider | 按上传顺序循环调用并顺序汇总 |
| 候选聚合 | 单图候选 | 跨图顺序拼接，不自动去重；最终以用户 PUT 确认为准 |
| 失败规则 | 单次请求失败 | 批次原子失败，不公开部分成功状态 |
| 数据库存储 | 单个对象名、扁平 raw detections | 对象名数组、按图片分组的 raw detections |

## 直接受影响 Owner

- 闫灿宇：维护 `docs/contracts/api_v1.md`、裁决契约冲突和控制合并顺序。
- 刘楚涵：多图选择、预览、删除、上传、逐图展示，以及数量、格式、单张/整批大小和批次失败提示。
- 绕家辉：多图 Food API、Service 循环、候选顺序汇总、`image_index`、MinIO 对象、Repository、ORM 和唯一 migration。
- 黄小石：确认单图 `FoodRecognitionProvider.recognize` 输入输出保持不变，并提供可被 Service 重复调用的实现。
- 吴雯：更新现有两个 Food canonical fixtures 和 Food 契约测试，不创建多图专用第二套 fixture。

## 暂不受影响模块

- Recipe API、Recipe JSON、固定 Prompt 和最小生成 Graph 不变。
- 陈煜君仍只通过 Repository 读取最终 `confirmed_ingredients`；本次不扩大她的任务，也不处理或合并其当前分支。
- 李晨宁负责的 Recipe 展示、Chat页面及四类 SSE 不变。
- Chat API、`token`、`recipe_updated`、`done`、`error` 事件和错误载荷不变。
- 黄小石的单图模型输出 `ModelDetection{class_name,confidence,bbox}` 不增加批次字段。

## 需要更新的 fixture 和测试

吴雯在契约 V1.1 合入 `develop` 后更新：

1. `food_recognition_success.json`：至少两张图片；`images` 顺序固定；每个模型候选含整数 `image_index`；bbox 能定位到对应图片。
2. `food_recognition_empty.json`：保留一至五张图片，`ingredients` 严格为 `[]`。
3. `test_food_contract.py`：覆盖 1 张、5 张成功，0 张和 6 张失败，单张 10 MB、整批 50 MB、格式和解码校验。
4. 增加一张图片无检测但其他图片成功的用例，确认它不是部分失败。
5. 增加任意文件或 Provider 失败导致整批失败的用例，禁止 `partial_success`。
6. `recipe_success.json`、`sse_recipe_update.txt` 及其契约测试不因 V1.1 改字段。

本契约 PR 不修改 fixture 实际文件，也不声称上述测试已经运行通过。

## 已有代码如何通过 Adapter 迁移

1. 对外路由只接收 `images`，即使只有一张也构造长度为 1 的列表。
2. Food Service Adapter 对每张图片复用现有单图保存、解码和 Provider 调用逻辑。
3. Adapter 给每个检测结果补充上传顺序对应的 `image_index`，再按 `image_index` 和单图检测顺序拼接候选。
4. Repository Adapter 把旧单个对象名包装成单元素列表，把旧扁平检测结果包装成 `image_index=0` 的分组。
5. 对外响应统一转换为 `images` 数组；不得同时返回旧 `image_url` 顶层字段。
6. Adapter 只用于复用内部单图能力，不得把旧 `image` 字段继续暴露为长期兼容入口。

## 合并顺序

1. 闫灿宇的 V1.1 契约和计划 PR 先合入 `develop`。
2. 吴雯从最新 `develop` 更新两个 Food fixtures 和契约测试并合入。
3. 绕家辉从最新 `develop` 完成 Food API、Service、Repository、ORM 和唯一 migration；黄小石确认单图 Provider 可重复调用。
4. 刘楚涵在最新 canonical fixture 和 Food API 契约上完成多图前端。
5. 所有个人分支通过 PR 合入 `develop` 后，在 `develop` 执行 Mock 联调，再切真实 Provider。
6. 陈煜君当前阶段分支继续独立修正，本次多图契约不触发其合并。

## 回滚方式

- V1.1 尚未合并或部署时：关闭或撤回对应文档/实现 PR，各成员回到最新 `develop`，不得用强推改写历史。
- V1.1 已合并但业务实现尚未合并时：通过正常 revert PR 回退契约提交，同时撤回尚未合入的多图实现 PR。
- V1.1 已部署并产生多图数据后：不得直接删除 `image_object_names` 或按图 raw detections；由绕家辉提供经过验证的 migration 回滚或数据转换方案，经闫灿宇确认后执行。
- 回滚期间也只允许一个公开请求格式，不得临时长期并存 `image` 和 `images`。

## 合并前仍需项目经理复核

- 每批最多 5 张是否符合演示和服务器容量。
- 50 MB 整批上限是否需要在真实部署环境下进一步收紧。
- 批次原子失败是否符合最终产品体验；V1.1 当前不接受部分成功。

上述参数如需调整，只修改唯一文件 `docs/contracts/api_v1.md` 并同步本迁移说明、计划、fixture 和契约测试，不创建 `api_v2.md` 或多图副本。
