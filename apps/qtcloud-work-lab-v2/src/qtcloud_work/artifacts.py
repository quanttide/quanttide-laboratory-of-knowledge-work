"""产物：工作流执行留下的东西，按类别分家。

规格：产物（Artifact）有名字与类别（见 specification/piece/artifact.md）。本 app 先立
日志与报告两类，落点由工作区按名字算（算法实验室自定）：类别取目录名，名字取工单名。

判据里用 `{{report}}` / `{{journal}}` 指这单的落点——不写死名字，一份定义开多单也不串。
"""

from pathlib import Path

JOURNAL = "journal"
REPORT = "report"


def path_of(workspace, kind: str, name: str) -> Path:
    return workspace.artifacts_dir / kind / f"{name}.md"


def journal_path(workspace, name: str) -> Path:
    return path_of(workspace, JOURNAL, name)


def report_path(workspace, name: str) -> Path:
    return path_of(workspace, REPORT, name)


def write_journal(workspace, name: str, words: str) -> Path:
    """日志收叙事：一段一段往下写，别的节原样保留。"""
    path = journal_path(workspace, name)
    text = path.read_text(encoding="utf-8") if path.is_file() else f"# 日志：{name}\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{text.rstrip()}\n\n{words.strip()}\n", encoding="utf-8")
    return path
