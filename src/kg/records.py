"""两种记录的段位与骨架：契约（约定要什么、怎么验收）与案卷（一件交付的完整过程）。

段位是程序唯一的说法——工具核对、模板生成都从这里取，不在别处再写一遍。
"""

from pathlib import Path

CONTRACT_SECTIONS = ("目标", "输出形态", "必须包含", "检查项")
DOSSIER_SECTIONS = ("生成者产出", "审查者报告", "人类裁决", "最终成果")

CONTRACT_TEMPLATE = """# 契约：<一句话说清要什么>

## 目标

<要什么>

## 输出形态

<交付物的形态：文件、路径、范围>

## 必须包含

- <要素一>
- <要素二>

## 检查项

- [ ] 机械：目标侧文件已就位 `path:data/journal/README.md`
- [ ] 机械：旧位置的副本已删除 `absent:data/journal/old.md`
- [ ] 闸门：落点与源位置同构
"""

DOSSIER_TEMPLATE = """# 案卷：<一句话说清这是哪一件事>

## 生成者产出

- <谁、按哪份契约、交了什么>

## 审查者报告

- ✓ <机械核对通过的项>
- ⧗ <留给闸门的项>

## 人类裁决

<谁拍的板、决定是什么>

## 最终成果

- <最后交出什么、落在哪>
"""


def sections(path: Path) -> set[str]:
    """文件里真的写了哪几段。"""
    return {line[3:].strip() for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("## ")}


def missing_sections(path: Path, required: tuple[str, ...]) -> list[str]:
    """该有而没有的段位。"""
    found = sections(path)
    return [name for name in required if name not in found]
