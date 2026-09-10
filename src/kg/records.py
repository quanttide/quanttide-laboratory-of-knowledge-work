"""记录的样子：契约、报告、历史的段位与骨架。

段位是程序唯一的说法——工具核对、模板生成都从这里取，不在别处再写一遍。
报告侧重事件（谁做的、审了什么、谁拍板、交出什么），机器可生成；
历史侧重叙事，人写。
"""

from pathlib import Path

CONTRACT_SECTIONS = ("目标", "输出形态", "必须包含", "检查项")
REPORT_SECTIONS = ("生成者产出", "审查者报告", "人类裁决", "最终成果")
TASK_SECTIONS = ("目标", "步骤", "验收")
HISTORY_PLACEHOLDER = "（这个任务的来龙去脉，你写）"

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

REPORT_TEMPLATE = """# 报告：{title}

## 生成者产出

## 审查者报告

## 人类裁决

## 最终成果
"""

HISTORY_TEMPLATE = """# 历史：{title}

{placeholder}
"""


def contract_template(about: str = "") -> str:
    """以某件已有的东西为题立契约：目标里点名，必须包含里写下来源。"""
    if not about:
        return CONTRACT_TEMPLATE
    text = CONTRACT_TEMPLATE.replace("<要什么>", f"改 `{about}`：<要什么>")
    return text.replace("- <要素一>", f"- 来源：`{about}`")


TASK_TEMPLATE = """# 任务：{title}

## 目标

{goal}

## 步骤

- <怎么走，一步一步>

## 验收

- [ ] 机械：<能写成断言的> `path:data/journal/README.md`
- [ ] 闸门：<只能人拍板的>
"""


def task_template(title: str = "", goal: str = "<要什么，一句话>") -> str:
    """任务的指令：按手册的三段——目标 / 步骤 / 验收。"""
    return TASK_TEMPLATE.format(title=title or "<任务的名字>", goal=goal or "<要什么，一句话>")


def report_template(title: str = "") -> str:
    return REPORT_TEMPLATE.format(title=title or "<任务的名字>")


def history_template(title: str = "") -> str:
    return HISTORY_TEMPLATE.format(title=title or "<任务的名字>", placeholder=HISTORY_PLACEHOLDER)


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
        if not stripped or stripped.startswith("# ") or stripped.startswith("## ") or stripped == HISTORY_PLACEHOLDER:
            continue
        lines.append(stripped)
    return "\n".join(lines)


def sections(path: Path) -> set[str]:
    return set(read_sections(path))


def missing_sections(path: Path, required: tuple[str, ...]) -> list[str]:
    found = set(read_sections(path))
    return [name for name in required if name not in found]
