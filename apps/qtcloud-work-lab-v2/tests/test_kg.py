#!/usr/bin/env python3
"""程序自带测试：不用额外依赖，干净检出上直接跑。

  python3 tests/test_kg.py

夹具全在临时目录里现搭：不碰真工作区，也不碰网络的。
"""

import json
import sys
import tempfile
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LAB / "src"))

from kg import actions, artifacts, cli, events, execute  # noqa: E402
from kg import ids as ids_layer  # noqa: E402
from kg import material as material_layer  # noqa: E402
from kg import workorder, workspace as workspace_layer  # noqa: E402
from kg import workflow as flow  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def test(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))


def make(tmp: Path, name: str = "ws"):
    """现搭一个工作区：身份首跑生成，目录齐备。"""
    return workspace_layer.Workspace(Path(tmp) / name)


def expect_error(where: str, kind: type, action) -> None:
    try:
        action()
    except kind:
        test(where, True)
        return
    except Exception as error:  # noqa: BLE001
        test(where, False, f"抛了 {type(error).__name__}: {error}")
        return
    test(where, False, "该报错却没报")


def clone(payload: dict) -> dict:
    return json.loads(json.dumps(payload))


def identity(tmp: Path) -> None:
    """工作区身份：缺则首跑生成。"""
    with tempfile.TemporaryDirectory() as inner:
        ws = make(Path(inner), "我的工作区")
        payload = ws.identity()
        test("身份：首跑生成 workspace.yaml", ws.identity_file.is_file())
        test("身份：六枚字段齐备", set(payload) == set(workspace_layer.FIELDS), str(sorted(payload)))
        test("身份：id 是 UUID", ids_layer.is_id(payload["id"]))
        test("身份：名字取目录名", payload["name"] == "我的工作区", payload["name"])
        test("身份：目录齐备", ws.workflows_dir.is_dir() and ws.workorders_dir.is_dir())
        again = make(Path(inner), "我的工作区").identity()
        test("身份：再读不换 id", again["id"] == payload["id"])


def _with_criteria(payload: dict, criteria: list[dict]) -> dict:
    changed = clone(payload)
    changed["steps"][0]["criteria"] = criteria
    return changed


def definition(tmp: Path) -> None:
    """工作流：写、读、列、核，schema 严格。"""
    with tempfile.TemporaryDirectory() as inner:
        ws = make(Path(inner))
        payload = flow.create(ws, "课程档案比对", ["定位", "比对", "结论"], "比对两边的档案")
        test("工作流：一文件一条，落在 workflows/", flow.file_for(ws, "课程档案比对").is_file())
        test("工作流：顶层四枚字段", set(payload) == set(flow.TOP_FIELDS), str(sorted(payload)))
        test("工作流：id 是 UUID", ids_layer.is_id(payload["id"]))
        test("工作流：步骤按写的顺序串起来", [item["name"] for item in flow.steps(payload)] == ["定位", "比对", "结论"])
        step_ids = [item["id"] for item in flow.steps(payload)]
        test("工作流：每步带全局 id（互不相同）", all(ids_layer.is_id(item) for item in step_ids) and len(set(step_ids)) == 3)
        test("工作流：每步写了判据骨架", all(item["criteria"] for item in flow.steps(payload)))
        test("工作流：读得回来", flow.read(ws, "课程档案比对")["name"] == "课程档案比对")
        test("工作流：列得出来", [item["name"] for item in flow.listing(ws)] == ["课程档案比对"])
        expect_error("工作流：撞名即拒", FileExistsError, lambda: flow.create(ws, "课程档案比对", ["一步"]))

        good = flow.read(ws, "课程档案比对")
        expect_error("schema：顶层多一个字段即报错", flow.WorkflowError, lambda: flow.validate({**good, "extra": 1}))
        expect_error("schema：少了 id 即报错", flow.WorkflowError, lambda: flow.validate({key: value for key, value in good.items() if key != "id"}))
        bad = clone(good)
        bad["steps"][1]["name"] = bad["steps"][0]["name"]
        expect_error("schema：步骤重名即报错", flow.WorkflowError, lambda: flow.validate(bad))
        bad = clone(good)
        bad["steps"][1]["id"] = bad["steps"][0]["id"]
        expect_error("schema：步骤 id 撞号即报错", flow.WorkflowError, lambda: flow.validate(bad))
        expect_error("schema：判据只写一半（file 无 contains）即报错", flow.WorkflowError, lambda: flow.validate(_with_criteria(good, [{"executor": "rule", "file": "a.md"}])))
        expect_error("schema：rule 写两种判法即报错", flow.WorkflowError, lambda: flow.validate(_with_criteria(good, [{"executor": "rule", "path": "a", "run": "true"}])))
        expect_error("schema：agent 判据不带 description 即报错", flow.WorkflowError, lambda: flow.validate(_with_criteria(good, [{"executor": "agent"}])))
        expect_error("schema：agent 判据带 rule 字段即报错", flow.WorkflowError, lambda: flow.validate(_with_criteria(good, [{"executor": "agent", "description": "审一下", "path": "a"}])))
        expect_error("schema：不认识的判据字段即报错", flow.WorkflowError, lambda: flow.validate(_with_criteria(good, [{"executor": "rule", "path": "a", "note": "旧写法"}])))


def check_definition(tmp: Path) -> None:
    """定义核对：路径在不在区内、小节有没有判据覆盖（不访问文件系统）。"""
    with tempfile.TemporaryDirectory() as inner:
        ws = make(Path(inner))
        flow.create(ws, "试一条", ["结论"])
        test("核对：骨架（占位路径）放行", flow.check(ws, "试一条") == [])
        payload = flow.read(ws, "试一条")
        payload["steps"][0]["description"] = "写完「结论」这一节"
        flow.file_for(ws, "试一条").write_text(flow.dump(payload), encoding="utf-8")
        test("核对：描述提到的小节没有判据覆盖，报出来", any("结论" in item for item in flow.check(ws, "试一条")))
        payload["steps"][0]["criteria"].append({"executor": "rule", "file": "out.md", "contains": "## 结论"})
        flow.file_for(ws, "试一条").write_text(flow.dump(payload), encoding="utf-8")
        test("核对：补上 contains 就过", flow.check(ws, "试一条") == [])
        payload["steps"][0]["criteria"][0] = {"executor": "rule", "path": "../逃出去.md"}
        flow.file_for(ws, "试一条").write_text(flow.dump(payload), encoding="utf-8")
        test("核对：路径逃出工作区，报出来", any("不在工作区内" in item for item in flow.check(ws, "试一条")))


def carry(tmp: Path) -> None:
    """导出与导入：原样带走；重名挡，凭证撞号挡。"""
    with tempfile.TemporaryDirectory() as inner:
        home = make(Path(inner), "home")
        away = make(Path(inner), "away")
        payload = flow.create(home, "带走的流程", ["步", "做"], "试一份可带走的工作流")
        target = Path(inner) / "带走的流程.yaml"
        flow.export(home, "带走的流程", target)
        test("导出：文件落地", target.is_file())
        imported = flow.import_(away, target)
        test("导入：落进另一个工作区", flow.file_for(away, "带走的流程").is_file())
        test("导入：步骤一字不差（凭证原样走）", imported["steps"] == payload["steps"])
        expect_error("导入：重名挡住", FileExistsError, lambda: flow.import_(away, target))

        local = make(Path(inner), "local")
        flow.create(local, "带走的流程", ["本地那一版"])
        expect_error("导入：本地已有同名（不同凭证）也挡住", FileExistsError, lambda: flow.import_(local, target))
        test("导入：换名字放行", flow.import_(local, target, "带走的流程·二")["name"] == "带走的流程·二")
        expect_error("导入：凭证撞号挡住（同一凭证不重发）", flow.WorkflowError, lambda: flow.import_(local, target, "带走的流程·三"))
        expect_error("导入：不是工作流的文件挡住", flow.WorkflowError, lambda: flow.import_(away, LAB / "README.md"))


def order_and_records(tmp: Path) -> None:
    """工单与工作记录：封面落笔即封，流水只增不改。"""
    with tempfile.TemporaryDirectory() as inner:
        ws = make(Path(inner))
        definition_payload = flow.create(ws, "试一条", ["定位", "比对", "结论"])
        order = workorder.create(ws, "试一次", "试一条", "试单")
        test("工单：一文件一单，落在 workorders/", workorder.file_for(ws, "试一次").is_file())
        test("工单：封面六枚字段（含流水）", set(order.payload) == set(workorder.FIELDS), str(sorted(order.payload)))
        test("工单：workflow_id 认到定义", order.workflow_id == definition_payload["id"])
        test("工单：流水一开始是空表", order.records == [])
        expect_error("工单：撞名即拒", FileExistsError, lambda: workorder.create(ws, "试一次", "试一条"))
        expect_error("工单：引不存在的工作流即拒", FileNotFoundError, lambda: workorder.create(ws, "另起一单", "没有这条"))

        first = workorder.append(order, ids_layer.new_id(), "定位", "两侧的源找齐了", is_succeeded=True)
        test("记录：seq 自 1 起", first["seq"] == 1)
        test("记录：step_id 账本查填", first["step_id"] == definition_payload["steps"][0]["id"])
        test("记录：order_id 对上工单", first["order_id"] == order.id)
        test("记录：八枚字段", set(first) == set(workorder.RECORD_FIELDS), str(sorted(first)))
        expect_error("记录：重放（同 id）即拒", workorder.OrderError, lambda: workorder.append(order, first["id"], "定位"))
        expect_error("记录：站名不在定义上即拒", workorder.OrderError, lambda: workorder.append(order, ids_layer.new_id(), "乱来"))
        expect_error("记录：时间倒序即拒", workorder.OrderError, lambda: workorder.append(order, ids_layer.new_id(), "比对", at="2000-01-01T00:00:00"))
        second = workorder.append(order, ids_layer.new_id(), "比对", "比完了", is_succeeded=True)
        test("记录：seq 递增不跳号", second["seq"] == 2)
        test("进度：按成功流水推导", workorder.progress(order) == "2/3")
        test("进度：下一步是结论", workorder.next_step(order)["name"] == "结论")
        test("进度：还没走完", not workorder.finished(order))
        test("闸门：待拍板清单列着结论", any("结论" in note for note in workorder.pending_gates(order)))
        expect_error("工单：有账不销", workorder.OrderError, lambda: workorder.delete(ws, "试一次"))

        tampered = clone(order.payload)
        tampered["records"][1]["seq"] = 3
        workorder.file_for(ws, "试一次").write_text(workorder.dump(tampered), encoding="utf-8")
        expect_error("账本：seq 断档即报错", workorder.OrderError, lambda: workorder.read(ws, "试一次"))
        workorder.file_for(ws, "试一次").write_text(workorder.dump(order.payload), encoding="utf-8")

        workorder.create(ws, "白纸", "试一条")
        workorder.delete(ws, "白纸")
        test("工单：没动工的白纸可删", not workorder.file_for(ws, "白纸").is_file())
        test("工单：列得出来（按工作流筛）", [item.name for item in workorder.listing(ws, "试一条")] == ["试一次"])
        test("记录：只增不改（旧记录原样在账上）", [record["seq"] for record in workorder.read(ws, "试一次").records] == [1, 2])


def _two_steps(ws) -> None:
    """把骨架改真：起步是机械站，闸门带 human 判据。"""
    payload = flow.create(ws, "试一条", ["起步", "闸门"])
    (ws.root / "out.md").write_text("# 结论\n\n了了。\n", encoding="utf-8")
    payload["steps"][0]["criteria"] = [{"executor": "rule", "description": "产物在", "path": "out.md"}]
    payload["steps"][1]["criteria"] = [{"executor": "human", "description": "创始人点头"}]
    flow.file_for(ws, "试一条").write_text(flow.dump(payload), encoding="utf-8")


def walking(tmp: Path) -> None:
    """走一步（智能体执行）与人记一笔（闸门放行）。"""
    with tempfile.TemporaryDirectory() as inner:
        ws = make(Path(inner))
        _two_steps(ws)
        workorder.create(ws, "试一次", "试一条")

        real_ai = execute.run_ai
        calls: list[str] = []

        def fake_ai(prompt: str, root: Path, timeout: int = 900) -> tuple[bool, str]:
            calls.append(prompt)
            return True, "我把这一步做完了"

        execute.run_ai = fake_ai
        try:
            stepped = actions.order_next(ws, "试一次")
            test("走一步：交给智能体跑", bool(calls) and "这一步：起步" in calls[0], str(calls[:1])[:60])
            test("走一步：核 rule 判据、记一条成功的流水", stepped.ok and workorder.progress(workorder.read(ws, "试一次")) == "1/2", str(stepped.lines))

            gated = actions.order_next(ws, "试一次")
            test("走一步：有闸门就等人放行", gated.ok and "等人放行" in "".join(gated.lines), str(gated.lines))
            test("走一步：闸门没放行就不落成功流水", workorder.progress(workorder.read(ws, "试一次")) == "1/2")

            released = actions.order_done(ws, "试一次", "闸门", "点头了")
            test("人记一笔：闸门放行落一条成功的流水", released.ok and workorder.finished(workorder.read(ws, "试一次")), str(released.lines))
        finally:
            execute.run_ai = real_ai

        test("日志：叙事落产物", actions.order_journal(ws, "试一次", "先起步，再等人点头。").ok and artifacts.journal_path(ws, "试一次").is_file())
        test("工单：走完是推导（不落字段）", workorder.finished(workorder.read(ws, "试一次")))


def journal_of_events(tmp: Path) -> None:
    """领域事件：三件都落 JSONL，负载带锚。"""
    with tempfile.TemporaryDirectory() as inner:
        ws = make(Path(inner))
        definition_payload = flow.create(ws, "试一条", ["一步"])
        events.workflow_created(ws, definition_payload)
        order = workorder.create(ws, "试一次", "试一条")
        events.workorder_created(ws, order.payload)
        record = workorder.append(order, ids_layer.new_id(), "一步", "做完了", is_succeeded=True)
        events.work_recorded(ws, order.payload, record)

        rows = events.listing(ws)
        test("事件：一条一行落 events.jsonl", [row["event"] for row in rows] == ["WorkflowCreated", "WorkOrderCreated", "WorkRecorded"], str([row["event"] for row in rows]))
        test("事件：工作流已创建带名字与工作区 id", rows[0]["name"] == "试一条" and rows[0]["workspace_id"] == ws.identity()["id"])
        test("事件：工单已创建带 id、名字、workflow_id 与全文", rows[1]["order_id"] == order.id and rows[1]["workflow_id"] == definition_payload["id"] and rows[1]["order"]["name"] == "试一次")
        test("事件：工作记录已追加带 id、seq、step_id 与全文", rows[2]["record_id"] == record["id"] and rows[2]["seq"] == 1 and rows[2]["step_id"] == definition_payload["steps"][0]["id"])
        test("事件：每行都是合法 JSON", all(json.loads(line)["event"] for line in ws.events_file.read_text(encoding="utf-8").splitlines() if line.strip()))


def command_line(tmp: Path) -> None:
    """命令行：走一遍真动作；头一个词是动词或旧写法都认。"""
    with tempfile.TemporaryDirectory() as inner:
        ws = Path(inner) / "ws"
        root = ["--root", str(ws)]
        test("命令行：workflow create", cli.main([*root, "workflow", "create", "试一条", "--steps", "甲,乙", "--description", "看看"]) == 0)
        test("命令行：workflow --new 也认（旧写法）", cli.main([*root, "workflow", "--new", "另一条", "--steps", "起"]) == 0)
        test("命令行：workflow list", cli.main([*root, "workflow", "list"]) == 0)
        test("命令行：workflow check 过", cli.main([*root, "workflow", "check", "试一条"]) == 0)
        test("命令行：order create", cli.main([*root, "order", "create", "试一次", "--workflow", "试一条"]) == 0)
        test("命令行：order list --json", cli.main([*root, "order", "list", "--json"]) == 0)
        test("命令行：order show", cli.main([*root, "order", "show", "试一次"]) == 0)

        target = workspace_layer.Workspace(ws)
        payload = flow.read(target, "试一条")
        payload["steps"][0]["criteria"] = [{"executor": "rule", "description": "工作区在", "path": "."}]
        payload["steps"][1]["criteria"] = [{"executor": "human", "description": "创始人点头"}]
        flow.file_for(target, "试一条").write_text(flow.dump(payload), encoding="utf-8")

        real_ai = execute.run_ai
        execute.run_ai = lambda prompt, where, timeout=900: (True, "做完了")
        try:
            test("命令行：order next（旧写法 --next）", cli.main([*root, "order", "试一次", "--next"]) == 0)
        finally:
            execute.run_ai = real_ai
        test("命令行：order done（闸门站，人放行）", cli.main([*root, "order", "done", "试一次", "乙", "--note", "点头"]) == 0)
        test("命令行：order journal", cli.main([*root, "order", "journal", "试一次", "一段叙事。"]) == 0)
        test("命令行：order delete 有账即拒", cli.main([*root, "order", "delete", "试一次"]) == 1)
        test("命令行：没有的工单报错不崩", cli.main([*root, "order", "show", "没有这一单"]) == 1)
        test("命令行：catalog 走得通", cli.main([*root, "catalog"]) == 0)
        test("命令行：find 无此名报错", cli.main([*root, "find", "绝无此名"]) == 1)


def fake_brain(tmp: Path) -> Path:
    """现搭一个最小的工作区根（第二大脑的样子）：日志与档案里各放一篇。"""
    root = tmp / "brain"
    (root / "data" / "journal" / "iGuo").mkdir(parents=True)
    (root / "data" / "journal" / "2026-09-10.md").write_text("# 今天\n\n记一笔。\n", encoding="utf-8")
    (root / "data" / "profile" / "iGuo" / "materials" / "work").mkdir(parents=True)
    (root / "data" / "profile" / "iGuo" / "materials" / "work" / "index.md").write_text("# 知识工作\n\n**规矩**：落到实处。\n", encoding="utf-8")
    return root


def workspace_actions(tmp: Path) -> None:
    """工作区级动作（目录 / 找文档 / 审计 / 材料）：扫的是工作区根，只读时不动盘。"""
    with tempfile.TemporaryDirectory() as inner:
        root = fake_brain(Path(inner))
        lab = Path(inner) / "lab"
        ws = workspace_layer.Workspace(root, lab)

        found = actions.catalog(ws)
        test("目录：按资产表清点", any("journal" in line for line in found.lines) and any("profile" in line for line in found.lines))
        hit = actions.find(ws, "知识工作")
        test("找文档：认篇内标题", hit.ok and any("index.md" in line for line in hit.lines), str(hit.lines))
        test("找文档：查无此名就说不认识", not actions.find(ws, "绝无此名").ok)

        items = dict(material_layer.materials(root))
        journal = items["data/journal/2026-09-10.md"]
        profile = items["data/profile/iGuo/materials/work/index.md"]
        test("材料：四字段各就各位", journal.type == "md" and journal.content == "记一笔。" and journal.source == "journal/2026-09-10.md", f"{journal.source}")
        test("材料：时间取文件名里的日期", journal.created_at == "2026-09-10", journal.created_at)
        test("材料：阶段由位置承担", journal.stage == "原始" and profile.stage == "材料")

        test("只读动作不在根上乱建（身份 / 定义 / 账本都不写）", not (root / "workspace.yaml").exists() and not (root / "workflows").exists() and not lab.exists())

        report = actions.audit(ws)
        test("审计：缺的格子报出来", not report.ok and any("缺资产" in line for line in report.lines), str(report.lines[:3]))
        actions.audit(ws, make=True)
        test("审计：--make 补建格子", (root / "data" / "history" / "README.md").is_file())
        test("审计：独立仓库那三格不凭空建", not (root / "packages").exists())


def main() -> int:
    for group in (identity, definition, check_definition, carry, order_and_records, walking, journal_of_events, command_line, workspace_actions):
        with tempfile.TemporaryDirectory() as tmp:
            group(Path(tmp))

    for name, ok, detail in RESULTS:
        print(f"{'✓' if ok else '✗'} {name}" + (f"——{detail}" if detail and not ok else ""))
    bad = [name for name, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} 通过。")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
