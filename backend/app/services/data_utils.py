"""
数据集工具模块
提供数据集验证、格式转换、划分等功能
支持 VOC XML、COCO JSON、LabelMe JSON → YOLO TXT 格式转换
"""

import json
import os
import shutil
import random
from pathlib import Path
from typing import List, Dict, Optional
from xml.etree import ElementTree as ET

from app.core.logger import get_logger

logger = get_logger("data_utils")


def validate_dataset(images_dir: str, labels_dir: str, class_names: List[str]) -> Dict[str, any]:
    """
    验证数据集完整性

    Args:
        images_dir: 图像目录路径
        labels_dir: 标注目录路径
        class_names: 类别名称列表

    Returns:
        验证结果字典，包含 is_valid、errors、warnings、stats
    """
    errors = []
    warnings = []
    stats = {
        "total_images": 0,
        "total_labels": 0,
        "matched_pairs": 0,
        "unmatched_images": [],
        "unmatched_labels": [],
        "class_distribution": {},
    }

    # 获取图像文件列表
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
    images_path = Path(images_dir)
    labels_path = Path(labels_dir)

    if not images_path.exists():
        errors.append(f"图像目录不存在: {images_dir}")
        return {"is_valid": False, "errors": errors, "warnings": warnings, "stats": stats}

    if not labels_path.exists():
        errors.append(f"标注目录不存在: {labels_dir}")
        return {"is_valid": False, "errors": errors, "warnings": warnings, "stats": stats}

    # 收集图像和标注文件
    image_files = {f.stem: f for f in images_path.iterdir() if f.suffix.lower() in image_extensions}
    label_files = {f.stem: f for f in labels_path.iterdir() if f.suffix.lower() == ".txt"}

    stats["total_images"] = len(image_files)
    stats["total_labels"] = len(label_files)

    # 检查配对
    for stem, img_path in image_files.items():
        if stem in label_files:
            stats["matched_pairs"] += 1
        else:
            stats["unmatched_images"].append(str(img_path))

    for stem, lbl_path in label_files.items():
        if stem not in image_files:
            stats["unmatched_labels"].append(str(lbl_path))

    # 检查标注文件内容
    class_ids = set()
    for lbl_path in label_files.values():
        try:
            with open(lbl_path, "r") as f:
                for line_num, line in enumerate(f, 1):
                    parts = line.strip().split()
                    if len(parts) < 5:
                        errors.append(f"{lbl_path}:{line_num} - 格式错误，需要至少5个值")
                        continue

                    try:
                        class_id = int(parts[0])
                        class_ids.add(class_id)

                        # 验证坐标范围
                        for i, val in enumerate(parts[1:], 1):
                            coord = float(val)
                            if i <= 2 and not (0 <= coord <= 1):
                                warnings.append(f"{lbl_path}:{line_num} - 中心坐标应在[0,1]范围")
                            elif i > 2 and not (0 < coord <= 1):
                                warnings.append(f"{lbl_path}:{line_num} - 宽高应在(0,1]范围")
                    except ValueError as e:
                        errors.append(f"{lbl_path}:{line_num} - 数值解析错误: {e}")
        except Exception as e:
            errors.append(f"读取标注文件失败 {lbl_path}: {e}")

    # 检查类别ID是否在范围内
    max_class_id = max(class_ids) if class_ids else -1
    if max_class_id >= len(class_names):
        errors.append(f"类别ID超出范围: 最大ID={max_class_id}, 类别数={len(class_names)}")

    # 统计类别分布
    for class_id in class_ids:
        if 0 <= class_id < len(class_names):
            stats["class_distribution"][class_names[class_id]] = (
                stats["class_distribution"].get(class_names[class_id], 0) + 1
            )

    # 生成警告
    if stats["unmatched_images"]:
        warnings.append(f"有 {len(stats['unmatched_images'])} 张图像没有对应标注")
    if stats["unmatched_labels"]:
        warnings.append(f"有 {len(stats['unmatched_labels'])} 个标注文件没有对应图像")

    return {"is_valid": len(errors) == 0, "errors": errors, "warnings": warnings, "stats": stats}


def convert_voc_to_yolo(voc_path: str, output_dir: str, class_names: List[str]) -> Optional[str]:
    """
    VOC XML -> YOLO TXT 格式转换

    Args:
        voc_path: VOC XML 文件路径
        output_dir: 输出目录
        class_names: 类别名称列表

    Returns:
        生成的 YOLO TXT 文件路径，失败返回 None
    """
    try:
        tree = ET.parse(voc_path)
        root = tree.getroot()

        # 获取图像尺寸
        size = root.find("size")
        if size is None:
            logger.error(f"VOC 文件缺少 size 元素: {voc_path}")
            return None

        img_width = int(size.find("width").text)
        img_height = int(size.find("height").text)

        if img_width <= 0 or img_height <= 0:
            logger.error(f"图像尺寸无效: {voc_path}")
            return None

        # 转换标注
        yolo_lines = []
        for obj in root.findall("object"):
            class_name = obj.find("name").text
            if class_name not in class_names:
                logger.warning(f"未知类别 {class_name}，跳过")
                continue

            class_id = class_names.index(class_name)
            bbox = obj.find("bndbox")

            xmin = float(bbox.find("xmin").text)
            ymin = float(bbox.find("ymin").text)
            xmax = float(bbox.find("xmax").text)
            ymax = float(bbox.find("ymax").text)

            # 转换为 YOLO 格式 (中心x, 中心y, 宽, 高) 归一化
            x_center = ((xmin + xmax) / 2) / img_width
            y_center = ((ymin + ymax) / 2) / img_height
            width = (xmax - xmin) / img_width
            height = (ymax - ymin) / img_height

            # 确保值在 [0, 1] 范围内
            x_center = max(0, min(1, x_center))
            y_center = max(0, min(1, y_center))
            width = max(0, min(1, width))
            height = max(0, min(1, height))

            yolo_lines.append(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")

        # 写入文件
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, Path(voc_path).stem + ".txt")
        with open(output_path, "w") as f:
            f.write("\n".join(yolo_lines))

        return output_path

    except Exception as e:
        logger.error(f"VOC 转换失败 {voc_path}: {e}")
        return None


def convert_coco_to_yolo(coco_json_path: str, output_dir: str, image_dir: str) -> Dict[str, str]:
    """
    COCO JSON -> YOLO TXT 格式转换

    Args:
        coco_json_path: COCO JSON 文件路径
        output_dir: 输出目录
        image_dir: 图像目录（用于获取图像尺寸）

    Returns:
        字典 {图像文件名: YOLO标注文件路径}
    """
    try:
        with open(coco_json_path, "r") as f:
            coco_data = json.load(f)

        # 构建类别映射
        categories = {cat["id"]: idx for idx, cat in enumerate(coco_data["categories"])}

        # 构建图像信息映射
        images = {img["id"]: img for img in coco_data["images"]}

        # 按图像分组标注
        annotations_by_image = {}
        for ann in coco_data["annotations"]:
            image_id = ann["image_id"]
            if image_id not in annotations_by_image:
                annotations_by_image[image_id] = []
            annotations_by_image[image_id].append(ann)

        os.makedirs(output_dir, exist_ok=True)
        result = {}

        # 转换每个图像的标注
        for image_id, img_info in images.items():
            img_width = img_info["width"]
            img_height = img_info["height"]
            file_name = img_info["file_name"]

            yolo_lines = []
            for ann in annotations_by_image.get(image_id, []):
                class_id = categories[ann["category_id"]]
                bbox = ann["bbox"]  # [x, y, width, height]

                # 转换为 YOLO 格式
                x_center = (bbox[0] + bbox[2] / 2) / img_width
                y_center = (bbox[1] + bbox[3] / 2) / img_height
                width = bbox[2] / img_width
                height = bbox[3] / img_height

                yolo_lines.append(
                    f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"
                )

            # 写入文件
            stem = Path(file_name).stem
            output_path = os.path.join(output_dir, stem + ".txt")
            with open(output_path, "w") as f:
                f.write("\n".join(yolo_lines))

            result[file_name] = output_path

        return result

    except Exception as e:
        logger.error(f"COCO 转换失败 {coco_json_path}: {e}")
        return {}


def convert_labelme_to_yolo(
    labelme_json_path: str, output_dir: str, class_names: List[str]
) -> Optional[str]:
    """
    LabelMe JSON -> YOLO TXT 格式转换

    Args:
        labelme_json_path: LabelMe JSON 文件路径
        output_dir: 输出目录
        class_names: 类别名称列表

    Returns:
        生成的 YOLO TXT 文件路径，失败返回 None
    """
    try:
        with open(labelme_json_path, "r") as f:
            data = json.load(f)

        img_width = data.get("imageWidth", 0)
        img_height = data.get("imageHeight", 0)

        if img_width <= 0 or img_height <= 0:
            logger.error(f"图像尺寸无效: {labelme_json_path}")
            return None

        yolo_lines = []
        for shape in data.get("shapes", []):
            class_name = shape.get("label", "")
            if class_name not in class_names:
                logger.warning(f"未知类别 {class_name}，跳过")
                continue

            class_id = class_names.index(class_name)
            points = shape.get("points", [])

            if len(points) < 2:
                continue

            # 获取边界框
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]

            xmin, xmax = min(xs), max(xs)
            ymin, ymax = min(ys), max(ys)

            # 转换为 YOLO 格式
            x_center = ((xmin + xmax) / 2) / img_width
            y_center = ((ymin + ymax) / 2) / img_height
            width = (xmax - xmin) / img_width
            height = (ymax - ymin) / img_height

            yolo_lines.append(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")

        # 写入文件
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, Path(labelme_json_path).stem + ".txt")
        with open(output_path, "w") as f:
            f.write("\n".join(yolo_lines))

        return output_path

    except Exception as e:
        logger.error(f"LabelMe 转换失败 {labelme_json_path}: {e}")
        return None


def split_dataset(
    images_dir: str,
    labels_dir: str,
    output_dir: str,
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
    seed: int = 42,
) -> Dict[str, int]:
    """
    划分数据集为训练集、验证集、测试集

    Args:
        images_dir: 图像目录
        labels_dir: 标注目录
        output_dir: 输出目录
        train_ratio: 训练集比例
        val_ratio: 验证集比例
        test_ratio: 测试集比例
        seed: 随机种子

    Returns:
        各集合数量统计
    """
    # 验证比例
    total_ratio = train_ratio + val_ratio + test_ratio
    if abs(total_ratio - 1.0) > 0.001:
        raise ValueError(f"比例之和应为1.0，当前为{total_ratio}")

    # 获取配对的文件
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
    images_path = Path(images_dir)
    labels_path = Path(labels_dir)

    image_files = {f.stem: f for f in images_path.iterdir() if f.suffix.lower() in image_extensions}
    label_files = {f.stem: f for f in labels_path.iterdir() if f.suffix.lower() == ".txt"}

    # 只保留配对的文件
    paired_stems = set(image_files.keys()) & set(label_files.keys())
    paired_list = sorted(list(paired_stems))

    # 随机打乱
    random.seed(seed)
    random.shuffle(paired_list)

    # 计算划分点
    total = len(paired_list)
    train_end = int(total * train_ratio)
    val_end = train_end + int(total * val_ratio)

    splits = {
        "train": paired_list[:train_end],
        "val": paired_list[train_end:val_end],
        "test": paired_list[val_end:],
    }

    # 创建输出目录并复制文件
    stats = {}
    for split_name, stems in splits.items():
        split_img_dir = os.path.join(output_dir, "images", split_name)
        split_lbl_dir = os.path.join(output_dir, "labels", split_name)
        os.makedirs(split_img_dir, exist_ok=True)
        os.makedirs(split_lbl_dir, exist_ok=True)

        for stem in stems:
            # 复制图像
            src_img = image_files[stem]
            dst_img = os.path.join(split_img_dir, src_img.name)
            shutil.copy2(src_img, dst_img)

            # 复制标注
            src_lbl = label_files[stem]
            dst_lbl = os.path.join(split_lbl_dir, src_lbl.name)
            shutil.copy2(src_lbl, dst_lbl)

        stats[split_name] = len(stems)
        logger.info(f"{split_name}: {len(stems)} 个样本")

    return stats


def generate_data_yaml(
    output_path: str,
    class_names: List[str],
    dataset_dir: str,
    train_dir: str = "images/train",
    val_dir: str = "images/val",
    test_dir: str = "images/test",
) -> str:
    """
    生成 data.yaml 配置文件

    Args:
        output_path: 输出文件路径
        class_names: 类别名称列表
        dataset_dir: 数据集根目录
        train_dir: 训练集相对路径
        val_dir: 验证集相对路径
        test_dir: 测试集相对路径

    Returns:
        生成的文件路径
    """
    yaml_content = f"""# YOLO 数据集配置文件
# 由 data_utils.py 自动生成

path: {dataset_dir}  # 数据集根目录
train: {train_dir}  # 训练集相对路径
val: {val_dir}  # 验证集相对路径
test: {test_dir}  # 测试集相对路径

# 类别数量
nc: {len(class_names)}

# 类别名称
names:
"""

    for i, name in enumerate(class_names):
        yaml_content += f"  {i}: {name}\n"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(yaml_content)

    logger.info(f"已生成 data.yaml: {output_path}")
    return output_path
