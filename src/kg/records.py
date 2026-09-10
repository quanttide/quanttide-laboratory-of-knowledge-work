"""记录的样子：契约、报告、历史的段位与骨架。

段位是程序唯一的说法——工具核对、模板生成都从这里取，不在别处再写一遍。
报告侧重事件（谁做的、审了什么、谁拍板、交出什么），机器可生成；
历史侧重叙事，人写。
"""

from pathlib import Path

REPORT_SECTIONS = ("执行记录", "闸门项")
JOURNAL_PLACEHOLDER = "（这个任务的来龙去脉，你写）"

REPORT_TEMPLATE = """# 报告：{title}

## 执行记录

## 闸门项
"""

JOURNAL_TEMPLATE = """# 日志：{title}

{placeholder}
"""




def report_template(title: str = "") -> str:
    return REPORT_TEMPLATE.format(title=title or "<任务的名字>")


def journal_template(title: str = "") -> str:
    return JOURNAL_TEMPLATE.format(title=title or "<任务的名字>", placeholder=JOURNAL_PLACEHOLDER)


def read_sections(path: Path) -> dict[str, list[str]]:
    """按二级标题切段，段里的条目取成列表（空行、散句与模板占位都不算）。"""
    text: dict[str, list[str]] = {}
    current = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            text[current] = []
        elif current and line.strip().startswith("- "):
            item = line.strip()[2:].strip()
            if item and "<" not in item:
                text[current].append(item)
    return text


def prose(path: Path) -> str:
    """正文：去掉标题与占位行之后剩下的那些话。"""
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("# ") or stripped.startswith("## ") or stripped == JOURNAL_PLACEHOLDER:
            continue
        lines.append(stripped)
    return "\n".join(lines)


def sections(path: Path) -> set[str]:
    return set(read_sections(path))


def missing_sections(path: Path, required: tuple[str, ...]) -> list[str]:
    found = set(read_sections(path))
    return [name for name in required if name not in found]
