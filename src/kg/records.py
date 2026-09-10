"""记录的样子：契约、案卷、一件事的段位与骨架。

段位是程序唯一的说法——工具核对、模板生成都从这里取，不在别处再写一遍。
"""

from pathlib import Path

CONTRACT_SECTIONS = ("目标", "输出形态", "必须包含", "检查项")
DOSSIER_SECTIONS = ("生成者产出", "审查者报告", "人类裁决", "最终成果")
CASE_SECTIONS = ("材料", "契约", "产出", "案卷")

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

CASE_TEMPLATE = """# 一件事：<一句话说清这是哪件事>

## 材料

- `<还没做成成品的输入，如 data/journal/2026-09-10.md>`

## 契约

- `<约定要什么、怎么验收>`

## 产出

- `<做出来的东西落在哪>`

## 案卷

- `<这次交付的记录>`
"""


def contract_template(about: str = "") -> str:
    """以某件已有的东西为题立契约：目标里点名，必须包含里写下来源。"""
    if not about:
        return CONTRACT_TEMPLATE
    text = CONTRACT_TEMPLATE.replace("<要什么>", f"改 `{about}`：<要什么>")
    return text.replace("- <要素一>", f"- 来源：`{about}`")


def dossier_template(about: str = "") -> str:
    return DOSSIER_TEMPLATE.replace("<一句话说清这是哪一件事>", about) if about else DOSSIER_TEMPLATE


def case_template(about: str = "") -> str:
    return CASE_TEMPLATE.replace("<一句话说清这是哪件事>", about) if about else CASE_TEMPLATE


def sections(path: Path) -> set[str]:
    """文件里真的写了哪几段。"""
    return set(read_sections(path))


def read_sections(path: Path) -> dict[str, list[str]]:
    """按二级标题切段，段里的条目取成列表（空行与非条目的散句都不算）。"""
    text: dict[str, list[str]] = {}
    current = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            text[current] = []
        elif current and line.strip().startswith("- "):
            item = line.strip()[2:].strip()
            if item and "<" not in item:  # 模板里的占位（<…>）不算数
                text[current].append(item)
    return text


def missing_sections(path: Path, required: tuple[str, ...]) -> list[str]:
    """该有而没有的段位。"""
    found = set(read_sections(path))
    return [name for name in required if name not in found]
