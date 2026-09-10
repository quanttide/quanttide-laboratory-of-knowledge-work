#!/usr/bin/env python3
"""程序自带测试：不用额外依赖，干净检出上直接跑。

  python3 tests/test_kg.py

两套夹具：真实工作区（集成，会因仓库变脏报红）与临时目录里现搭的假仓库（单元，不碰真文件）。
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LAB / "src"))

from kg import assets as assets_layer  # noqa: E402
from kg import catalog as catalog_layer  # noqa: E402
from kg import checks as checks_layer  # noqa: E402
from kg import cli, material as material_layer  # noqa: E402
from kg import records  # noqa: E402
from kg import report  # noqa: E402
from kg import task as task_layer  # noqa: E402
from kg import workflow as flow_layer  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []
TASK_OK = """# 任务：核对

## 目标

看结果对不对。

## 步骤

- 跑一遍判据

## 验收

- [ ] 机械：日志在 `path:data/journal/README.md`
- [ ] 闸门：创始人过目
"""


def test(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))


def fake_repo(tmp: Path, stray: bool = False) -> Path:
    """按资产表搭一个齐备的假工作区，可选塞一个未登记目录。"""
    root = tmp / "second-brain"
    stated = {name for _, name in assets_layer.STATED}
    for asset in assets_layer.assets():
        if asset.name in assets_layer.LOCATION:
            continue
        (root / ("data" if asset.name in stated else "docs") / asset.name).mkdir(parents=True)
    (root / "packages" / "quanttide-demo-toolkit").mkdir(parents=True)
    (root / "apps" / "demo").mkdir(parents=True)
    (root / "examples" / "default").mkdir(parents=True)
    if stray:
        (root / "data" / "未登记目录").mkdir(parents=True)
    return root


def with_repo(root: Path) -> None:
    """装上 git 并提交一次，让材料的时间字段有处可取。"""
    for cmd in (["init", "-q"], ["add", "-A"], ["-c", "user.email=lab@example.com", "-c", "user.name=lab", "commit", "-qm", "首次提交"]):
        subprocess.run(["git", *cmd], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "--amend", "--date=2026-09-10T09:00:00", "--no-edit"], cwd=root, check=True, capture_output=True)


def workspace(real: Path) -> None:
    """工作区层面：资产表、目录、材料。"""
    test("契约是二十格", len(assets_layer.assets()) == 20, f"实得 {len(assets_layer.assets())}")
    test("真实工作区二十格齐备", not assets_layer.missing(real), f"缺 {[a.kind for a in assets_layer.missing(real)]}")

    with tempfile.TemporaryDirectory() as tmp:
        clean = fake_repo(Path(tmp) / "clean")
        test("假仓库：齐备时无缺资产", not assets_layer.missing(clean))
        test("假仓库：齐备时无未登记", not catalog_layer.build(clean).unregistered(clean))
        dirty = fake_repo(Path(tmp) / "dirty", stray=True)
        stray = catalog_layer.build(dirty).unregistered(dirty)
        test("假仓库：未登记目录被揪出", [p.name for p in stray] == ["未登记目录"], f"实得 {[p.name for p in stray]}")

    catalog = catalog_layer.build(real)
    test("按名词条命中规格", any("material.md" in str(e.path) for e in catalog.find("材料")))
    test("模糊兜底命中", bool(catalog.find("日志规范")))

    with tempfile.TemporaryDirectory() as tmp:
        root = fake_repo(Path(tmp) / "材料")
        (root / "data" / "journal" / "2026-09-10.md").write_text("# 今天\n\n记一笔。\n", encoding="utf-8")
        (root / "data" / "profile" / "iGuo.md").write_text("# 我\n\n档案一页。\n", encoding="utf-8")
        with_repo(root)
        found = dict(material_layer.materials(root))
        journal, profile = found["data/journal/2026-09-10.md"], found["data/profile/iGuo.md"]
        test("材料：四字段填得出", not journal.missing and not profile.missing)
        test("材料：时间取首次提交日期", journal.created_at == "2026-09-10", f"实得 {journal.created_at}")
        test("材料：阶段由位置承担", journal.stage == "原始" and profile.stage == "材料")


def judges(real: Path) -> None:
    """判据：结构化字段（机械带 spec、闸门只有说明），四种 spec 都能跑。"""
    defined = [
        {"type": "rule", "description": "目标侧文件已就位", "path": "data/journal/README.md"},
        {"type": "rule", "description": "旧文件已删除", "absent": "gone.md"},
        {"type": "rule", "description": "含某段文字", "file": "data/journal/README.md", "contains": "日志"},
        {"type": "rule", "description": "命令跑得通", "run": "test -f data/journal/README.md"},
        {"type": "rule", "path": "data/journal"},
        {"type": "human", "description": "落点与源位置同构"},
    ]
    with tempfile.TemporaryDirectory() as inner:
        root = Path(inner) / "repo"
        (root / "data" / "journal").mkdir(parents=True)
        (root / "data" / "journal" / "README.md").write_text("# 日志\n", encoding="utf-8")
        items = checks_layer.items_of(defined)
        results, gates = checks_layer.run(root, items)
        test("判据：rule 跑、human 留给人", len(results) == 5 and len(gates) == 1, f"rule {len(results)}，human {len(gates)}")
        test("判据：四种判法都跑得通", all(ok for _, ok, _ in results), str(results))
        test("判据：说明可省（按字段拼）", any(item.description == "存在：data/journal" for item, _, _ in results), str([i.description for i, _, _ in results]))
        (root / "gone.md").write_text("还在\n", encoding="utf-8")
        failed = [ok for _, ok, _ in checks_layer.run(root, items)[0]]
        test("判据：该报红时报红", failed.count(False) == 1, f"实得 {failed}")


def flow_and_task(real: Path) -> None:
    """工作流（串联步骤）与任务（一次执行）。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = fake_repo(Path(tmp) / "task")
        (root / "data" / "journal" / "2026-09-10.md").write_text("# 今天\n", encoding="utf-8")
        (root / "data" / "journal" / "README.md").write_text("# 日志\n", encoding="utf-8")
        data = Path(tmp) / "data"

        report.workflow_new(data, "试一条", ["定位", "比对", "结论"], "看看能不能串起来")
        flow = flow_layer.open_workflow(data, "试一条")
        test("工作流：步骤按写的顺序串起来", [s.name for s in flow.steps()] == ["定位", "比对", "结论"])
        test("工作流：每步自带判据骨架（默认 agent）", all(s.rules and s.executor == "agent" for s in flow.steps()))

        # 把「比对」这一步写成真的
        payload = flow_layer.load(flow.file)
        step = payload["steps"][1]
        step["description"] = "把两边比一遍"
        step["criteria"] = [
            {"type": "rule", "description": "日志在", "path": "data/journal/README.md"},
            {"type": "human", "description": "创始人过目"},
        ]
        flow.file.write_text(flow_layer.dump(payload), encoding="utf-8")
        flow.reload()

        # 把「写给 AI 跑」的那一环换掉：测试里不真调 pi
        real_ai = task_layer.run_ai
        calls: list[str] = []

        def fake_ai(prompt: str, where: Path, timeout: int = 900) -> tuple[bool, str]:
            calls.append(prompt)
            return True, "我把这一步做完了"

        task_layer.run_ai = fake_ai

        started = report.task_new(root, data, "试一次", "试一条", "把纪律落下来")
        task = task_layer.open_task(root, data, "试一次")
        test("任务：一件任务一个文件，指向工作流", task.file.is_file() and task.workflow_name() == "试一条", task.workflow_name())
        test("任务：状态按工作流列步骤", [row[0] for row in started.rows] == ["定位", "比对", "结论"])
        test("任务：起时记一笔", len(task.events()) == 1)
        auto = report.task_step(root, data, "试一次", "", auto=True)  # 默认执行者是 AI，交给 pi
        test("走一步：默认交给智能体跑", bool(calls) and "这一步：定位" in calls[0], str(calls[:1])[:60])
        test("走一步：AI 干活也记一笔", any("AI 执行" in e["detail"] for e in task.events()), str(task.events()[-1:]))

        # 标了「执行者：人」的步骤，程序不抢着做
        payload = flow_layer.load(flow.file)
        payload["steps"][1]["executor"] = "human"
        flow.file.write_text(flow_layer.dump(payload), encoding="utf-8")
        calls.clear()
        human = report.task_step(root, data, "试一次", "", auto=True)
        test("走一步：人做的步骤等人", human.ok and not calls and "轮到你" in "".join(human.lines), str(human.lines))
        task_layer.run_ai = real_ai

        step = report.task_step(root, data, "试一次", "比对", "比完了")
        test("走一步：判据通过", step.ok and any(row[1] == "✓" for row in step.rows), str(step.rows))
        test("走一步：闸门列出来", any(row[1] == "闸门" for row in step.rows))
        test("走一步：记账了", len(task.events()) == 3, f"实得 {len(task.events())}")
        test("走一步：下一步只剩结论", task.next_step().name == "结论")

        written = task.artifact("report.md").read_text(encoding="utf-8")
        test("报告：执行记录写下来了", "## 执行记录" in written and "比对" in written)
        test("报告：闸门项留给人", "## 闸门项" in written and "⧗" in written)

        report.task_history(root, data, "试一次", "先串步骤，再执行。")
        test("历史：叙事进 artifacts", records.prose(task.artifact("history.md")) != "")
        test("列任务：报工作流与下一步", report.task_list(root, data).rows[0][1] == "试一条")
        test("工作流里没有的步骤就报错", not report.task_step(root, data, "试一次", "乱来", "", None) if False else not report.task_step(root, data, "试一次", "乱来").ok)
        test("数据分三家放", task.file.is_relative_to(data / "tasks") and flow.file.is_relative_to(data / "workflows") and task.artifacts_dir.is_relative_to(data / "artifacts"))


def carry(real: Path) -> None:
    """工作流存下来，下次能导入用：导出 → 导进另一个数据仓，内容一字不差。"""
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "data-a"
        away = Path(tmp) / "data-b"
        report.workflow_new(home, "带走的流程", ["步", "做"], "试一份可带走的工作流")
        source = report.workflow_export(home, "带走的流程", Path(tmp) / "带走的流程.yaml")
        test("导出：文件落地（YAML，原样）", source.ok and (Path(tmp) / "带走的流程.yaml").is_file())

        here = flow_layer.open_workflow(home, "带走的流程")
        before = [(s.name, s.executor, s.criteria) for s in here.steps()]
        imported = report.workflow_import(away, Path(tmp) / "带走的流程.yaml")
        there = flow_layer.open_workflow(away, "带走的流程")
        test("导入：落进另一个数据仓", imported.ok and there.file.is_file() and there.file.is_relative_to(away))
        test("导入：步骤、执行者、判据一字不差", before == [(s.name, s.executor, s.criteria) for s in there.steps()], str(before))
        test("导入：重名挡住", not report.workflow_import(away, Path(tmp) / "带走的流程.yaml").ok)
        test("导入：换名字放行", report.workflow_import(away, Path(tmp) / "带走的流程.yaml", "带走的流程·二").ok)
        test("导入：不是工作流的文件挡住", not report.workflow_import(away, LAB / "README.md").ok)


def links(real: Path) -> None:
    """编号与补建。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "second-brain"
        (root / "data" / "journal").mkdir(parents=True)
        before = len(assets_layer.missing(root))
        report.audit(root, make=True)
        left = {asset.name for asset in assets_layer.missing(root)}
        test("审计：能补建缺的格子", len(assets_layer.missing(root)) < before and (root / "data" / "history" / "README.md").is_file())
        test("审计：独立仓库那三格不凭空建", left == set(assets_layer.LOCATION), f"剩 {sorted(left)}")


def gui_smoke(real: Path) -> None:
    """界面冒烟：装了 PySide6 的窗口模块就跑，没装就跳过。"""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication

        from kg import gui
    except ImportError:
        print("（未装 PySide6 窗口模块，跳过界面冒烟：pip install PySide6-Essentials）")
        return
    app = QApplication.instance() or QApplication([])
    window = gui.Window(real)
    browser = window.browser
    browser.select_action("目录")
    test("界面：目录出得了表", bool(browser.run_current().rows))
    browser.select_action("审计")
    test("界面：审计通过", browser.run_current().ok)
    browser.select_action("找文档")
    test("界面：空输入先拦住", not browser.run_current().ok)
    groups = [spec.group for spec in gui.SPECS]
    test("界面：浏览页分两组", groups == ["工作区", "工作区", "查看", "查看"], str(groups))

    with tempfile.TemporaryDirectory() as tmp:
        fake = fake_repo(Path(tmp) / "desk")
        (fake / "data" / "journal" / "2026-09-10.md").write_text("# 今天\n", encoding="utf-8")
        (fake / "data" / "journal" / "README.md").write_text("# 日志\n", encoding="utf-8")
        data = Path(tmp) / "data"
        desk = gui.Desk(fake, data)
        test("台面：没有运行时提示新建", "新建" in desk.next_label.text())
        flow_layer.create(data, "试一条", ["材料", "核对"], "把纪律落下来")
        task_layer.create(fake, data, "试一次", "试一条", "把纪律落下来")
        desk.reload()
        test("台面：步骤表按工作流列出", desk.steps_table.rowCount() == 2 and desk.steps_table.item(0, 2).text() == "—")
        desk.selected_step()
        report.task_step(fake, data, "试一次", "材料", "记了一条")
        desk.reload()
        test("台面：状态跟着走", desk.steps_table.item(0, 2).text() == "✓" and desk.log_table.rowCount() >= 2)
    window.close()
    del app


def main() -> int:
    real = assets_layer.repo_root()
    workspace(real)
    judges(real)
    flow_and_task(real)
    carry(real)
    links(real)
    gui_smoke(real)

    for name, ok, detail in RESULTS:
        print(f"{'✓' if ok else '✗'} {name}" + (f"——{detail}" if detail and not ok else ""))
    bad = [name for name, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} 通过。")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
