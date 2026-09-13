# 开发计划

实验室里的工具箱：一个程序，怎么继续长。

## 现状

```text
src/kg/
├── cli.py       命令行入口：八个动作 + gui（argparse，kg --help 即用法）
├── gui.py       窗口入口：同一套动作，左栏动作、右栏参数、下边结果
├── report.py    动作结果与动作之间的接口：命令行与窗口共用的一层
├── assets.py    资产层：二十格、落点规则、工作区根
├── catalog.py   目录层：扫描成名字索引（收文件名与篇内标题）
├── checks.py    判据：结构化判据（机械带 spec / 闸门只有说明）的执行
├── material.py  材料：类型 / 内容 / 来源 / 时间，阶段由位置承担
├── records.py   记录的段位与骨架：报告（执行记录 + 闸门项）、日志（叙事）
├── workflow.py  工作流（YAML）：严格 schema（name / description / steps；步骤 name / description / executor / criteria；判据 executor: rule|agent|human）
├── task.py      任务（YAML）：工作流的一次执行（运行上下文、走一步、流水、报告、日志）
└── __main__.py  python3 -m kg

tests/test_kg.py       自带测试，39 项（装 PySide6 窗口模块则多 7 项界面冒烟），不依赖 pytest
data/                  所有数据（工作纪律）：workflows/ 定义、tasks/（<任务>.yaml：start + workflow + 运行上下文 root/data/workflows + log 流水）、artifacts/{report,journal}/ 产物（按任务名）
kg / kg-gui            本目录下的启动器（不必安装）——全局 --root（工作区）、--data（数据仓：任务与产物草稿）、--workflows（工作流目录，默认 <数据仓>/workflows/）
pyproject.toml         打包：装上就是 kg 与 kg-gui 命令
```

代码在 `src/kg/`，说明在 `docs/`：`docs/user-guide/` 对外讲怎么用，`docs/index.md` 讲两种工作模式与三种记录，本文件讲怎么继续开发。

## 架构原则

1. **一个对象**：主界面是「当前这任务」，动作只是它的下一步；事实自动记进它的流水。工作区层面的动作（目录、审计）退到浏览页。
2. **数据在一个 app**：所有数据放本 app `data/`，不写到实验室外；**禁止过滤**——数据全量落位，扫描只许跳过版本库与构建产物（见 `AGENTS.md`）。
3. **一个程序**：一个包、一个入口。库不打印、不找路径，只接受传进来的参数；打印与定位归 `cli.py`。
4. **一份说法**：段位、判据、字段各只写一处（`records.py`、`checks.py`、`material.py`），模板与核对都从那里取。
5. **无服务端**：文档在文件里，索引现扫现生成；没有端点、没有数据库、没有后台进程。
6. **只读**：程序不改仓库内容，只写自己造的文件（骨架、导出）；真正的写入由人和 AI 在对话里做，提交走 git。
7. **命名两件套**：英文文件名定路径、中文标题定概念——查得到靠这两样，不靠额外元数据。

## 已落地

**① 一个入口** —— 早先四份碎片（`resolver.py`、`contract.py`、`dossier.py`、`material.py`）与两个命令行壳合成一个包；`repo_root` 收进资产层，别处不再各写一份。

**② 记录都进程序** —— 材料有 `kg material`（四字段现填）；指令与报告各有骨架（`new-`）与核对（`audit-`）；判据写在指令的「验收」段里，用反引号给出：

```markdown
- [ ] 机械：目标侧文件已就位 `path:docs/index.md`
- [ ] 机械：旧位置的副本已删除 `absent:docs/old.md`
- [ ] 机械：读了说明书 `contains:docs/index.md=第二大脑`
- [ ] 机械：命令跑得通 `run:test -f docs/index.md`
- [ ] 闸门：落点与源位置同构
```

四种判据——`path:` 存在、`absent:` 不存在、`contains:` 含某段文字、`run:` 命令退出码为零；路径相对工作区根，写绝对路径则按绝对路径（跨仓库核对用）。没有判据的条目是闸门项，原样列给人拍板。

**③ 抽样自证** —— `kg audit-instruction data/tasks/文档迁移/搬运.md` 与 `kg audit-report data/artifacts/文档迁移/report.md` 当场核对通过：格式在真事上验证过，不是只在样例上成立。

**④ 测试与打包** —— `python3 tests/test_kg.py` 17 项全通过（真工作区当集成夹具、临时目录当单元夹具）；`pyproject.toml` 一装就是 `kg` 命令，本目录下 `./kg` 也能跑。

**⑤ 图形入口** —— `kg gui` / `./kg-gui`：动作、参数、结果与命令行是同一套（`report.py` 出结果，命令行打印、界面画表），不重复算法。空输入先拦住、结果空表回退成文字、行里的文件双击就开、出错留在窗里。PySide6 的窗口模块可能被拆包，缺了会提示怎么补。

**⑥ 审计与导出** —— `kg audit --json 报告.json` 落出「结果 / 缺资产 / 未登记」；`kg catalog --json`、`kg material --json` 同理，给别的程序读。

**⑦ 工作流与运行成为主界面** —— 程序不预置编排：一次运行的工作流写在 `data/workflows/<运行>.md`（步骤清单），每步关联 `data/tasks/<运行>/<步骤>.md`（三段：目标 / 步骤 / 验收）；人执行的是任务，`kg run <名字> --done <步骤>` 跑该任务的验收判据、记一笔流水、刷新 `data/artifacts/<运行>/report.md`。窗口的「台面」就是这张步骤表加一个「执行这一步」。不做判例累积（按用户决定，减工程量）。

## 待办

**⑧ 能用 AI 跑的都用 AI** —— 步骤默认执行者是 AI：`kg task <名字> --next` 拼好提示（做什么 + 判据 + 产物落点）交给 `pi -p --no-session`，跑完由**程序**核对机械判据、记一笔（流水注明「AI 执行」）；标了 `- 执行者：人` 的步骤程序不抢着做。判据不许 AI 写或改（自评自过）。测试里 `task_layer.run_ai` 被替换，不真调 pi。

**⑨ 工作流可带走** —— `kg workflow --export <文件>` 原样存一份；`--import <文件> [--as 名字]` 导回来（先验「有没有 `### 步骤`」，重名挡、`--as` 换名）。换机器、换 `--data`、换仓库都能接着用；判据里的路径是那边的，导完要自己核一遍。

**⑩ 定义用 YAML，判据分三类** —— 工作流与任务改成 YAML，`workflow.py` 带**严格** schema（不认识的字段报错）；判据按主体分三类（判据的 `executor`）：`rule` 由规则引擎按字段判（`checks.items_of` → `checks.run`）、`agent` 由智能体照判准审（`task.py` 的 `judge_by_ai`）、`human` 留给人。判据字段化后，那套 `contains:文件=文字` 的小语法删了。报告/历史仍是 Markdown、流水是 JSONL。

**⑪ 毕业条件** —— 离开实验室、进工具箱仓（`packages/quanttide-work-toolkit`）之前要满足三条：动作在真实工作区上稳定跑通；测试守着；任务的格式（三段）被真实交付用过至少一次（已有一件）。

## 已决：曾经的重复

`contract/` 与 `dossier/` 原先各有一份 Python 对象版的结构，与程序重复。决定是**删代码、留样本**：结构只由程序拥有（同一套四段写在两处就是两份事实源）；样本搬进数据仓（`data/tasks/文档迁移/`、`data/artifacts/文档迁移/`），判例价值留着，代码的独有能力（判据写进指令文件、`run:` 判据跑命令）没丢。

## 不做的事

- 不做服务端、不做数据库、不做可视化面板；
- 不在实验室外改文件（产物、规格、手册一律不碰）；
- 不为「以后可能需要」提前加字段——材料四字段、任务三段、报告四段都是够用即可，多了就是负担。
