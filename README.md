# quanttide-laboratory-of-knowledge-work

量潮知识工作实验室——知识工作实验与原型。

## 一个程序：kg

中心是**任务**——从材料走到成果，中途发生的事都记进它的流水；命令与窗口里的动作，只是它的下一步。

```bash
./kg --help              # 本目录下直接跑；十个动作
./kg-gui                 # 开窗口版（同一个程序）
uv pip install -e .      # 或装成命令：kg / kg-gui
```

界面要 PySide6 的窗口模块——有些发行版把它拆开了（Debian/Ubuntu 上是 `python3-pyside6.qtwidgets`）：
缺了的话，实验室内建个虚拟环境即可，不动系统：

```bash
uv venv .venv && uv pip install -e ".[gui]"
.venv/bin/kg-gui
```

| 动作 | 干什么 |
|------|--------|
| `kg workflow --new <名字> --steps 甲,乙,丙` | 写一条工作流：步骤串联，每步自带验收判据 |
| `kg workflow <名字>` / `--list` | 看步骤与判据 / 有哪些工作流 |
| `kg task --new <名字> --workflow <工作流> [--about …]` | 起一件任务（工作流的一次执行） |
| `kg task <名字>` / `--list` | 看步骤状态与流水 / 有哪些任务 |
| `kg task <名字> --next` | 走下一步：执行者是 AI 的交给 `pi -p` 跑，然后**程序自己**核对判据、记账 |
| `kg task <名字> --done <步骤> [--note 一句话]` | 人做的那一步，记一笔 |
| `kg task <名字> --history <一段话>` | 历史：写下这一次的来龙去脉（叙事） |
| `kg find <名字>` | 按名找文档——认文件名与中文标题 |
| `kg catalog` | 看目录——列全部条目，可导 JSON |
| `kg audit [--make]` | 审计——资产表有而工作区无、工作区有而资产表无；`--make` 补建缺的格子 |
| `kg material [路径…]` | 看材料——类型、内容、来源、时间，阶段由位置承担 |
| `kg new-instruction [--about 目标]` / `kg audit-instruction [--into 报告]` | 写指令骨架（目标 / 步骤 / 验收）/ 核对指令：跑验收里的判据，可把审查者报告写进报告 |
| `kg new-report` / `kg audit-report` | 写报告骨架（事件四段）/ 核对报告 |
| `kg gui` | 开窗口——台面（当前这个任务）与浏览（工作区动作）两页 |

默认工作区从当前目录往上找，`--root` 可指向别的第二大脑。

## 目录

- `src/kg/` 程序：assets（资产层：二十格与落点）、catalog（目录层）、checks（判据）、material（材料）、records（记录段位与骨架：任务三段、报告四段、历史）、task（任务：状态机、动作、流水）、report（动作结果与动作之间的接口，命令行与界面共用）、cli（命令行入口）、gui（窗口入口）
- `data/` 所有数据（工作纪律，见 `AGENTS.md`），按领域模型分三家：`workflows/` 工作流（步骤与判据）、`tasks/` 任务（一次执行）、`artifacts/` 产物（log.jsonl、report.md、history.md）
- `tests/` 自带测试：`python3 tests/test_kg.py`，26 项；装了 PySide6 窗口模块则多 6 项界面冒烟，不依赖 pytest
- `docs/` 说明：模式与记录（index.md）、用户指南、开发计划

## 许可

[CC BY 4.0](LICENSE)
