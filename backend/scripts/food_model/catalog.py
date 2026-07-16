"""食品数据集的稳定类别元数据。

训练原始数据仍使用 Roboflow 导出的 30 个英文类别名。最终 V1 模型只会从中
选择 12 个类别，并使用 ``OUTPUT_CLASS_NAMES`` 中的单数、snake_case 名称作为
FoodRecognitionProvider 的 ``class_name`` 输出。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FoodClass:
    """一个原始数据集类别及其 V1 展示信息。"""

    source_name: str
    class_name: str
    display_name: str


FOOD_CLASSES: tuple[FoodClass, ...] = (
    FoodClass("apple", "apple", "苹果"),
    FoodClass("banana", "banana", "香蕉"),
    FoodClass("beef", "beef", "牛肉"),
    FoodClass("blueberries", "blueberry", "蓝莓"),
    FoodClass("bread", "bread", "面包"),
    FoodClass("butter", "butter", "黄油"),
    FoodClass("carrot", "carrot", "胡萝卜"),
    FoodClass("cheese", "cheese", "奶酪"),
    FoodClass("chicken", "chicken", "鸡肉"),
    FoodClass("chicken_breast", "chicken_breast", "鸡胸肉"),
    FoodClass("chocolate", "chocolate", "巧克力"),
    FoodClass("corn", "corn", "玉米"),
    FoodClass("eggs", "egg", "鸡蛋"),
    FoodClass("flour", "flour", "面粉"),
    FoodClass("goat_cheese", "goat_cheese", "山羊奶酪"),
    FoodClass("green_beans", "green_beans", "四季豆"),
    FoodClass("ground_beef", "ground_beef", "牛肉末"),
    FoodClass("ham", "ham", "火腿"),
    FoodClass("heavy_cream", "heavy_cream", "淡奶油"),
    FoodClass("lime", "lime", "青柠"),
    FoodClass("milk", "milk", "牛奶"),
    FoodClass("mushrooms", "mushroom", "蘑菇"),
    FoodClass("onion", "onion", "洋葱"),
    FoodClass("potato", "potato", "土豆"),
    FoodClass("shrimp", "shrimp", "虾"),
    FoodClass("spinach", "spinach", "菠菜"),
    FoodClass("strawberries", "strawberry", "草莓"),
    FoodClass("sugar", "sugar", "糖"),
    FoodClass("sweet_potato", "sweet_potato", "红薯"),
    FoodClass("tomato", "tomato", "番茄"),
)

SOURCE_NAMES = [item.source_name for item in FOOD_CLASSES]
BY_SOURCE_NAME = {item.source_name: item for item in FOOD_CLASSES}


def output_definition(source_name: str) -> FoodClass:
    """返回一个原始类别对应的 V1 模型输出定义。"""
    try:
        return BY_SOURCE_NAME[source_name]
    except KeyError as exc:  # pragma: no cover - callers validate YAML first
        raise ValueError(f"未知食品类别: {source_name}") from exc
