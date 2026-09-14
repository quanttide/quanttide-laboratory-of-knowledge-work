# 知识工作工具箱（v2）

程序的中心是工单——一条工作流的一次执行实例；命令里的每个动作，就是走其中一站。模型与行为差见[设计](../index.md)，里程碑与决策见[开发计划](../dev-guide/index.md)。

## 功能对表（v1 → v2）

v1 的每个动作在 v2 都有归属——沿用、收编或明说退役；规格没规定的动作标记「实验室自留」。程序名 `qtcloud-work`（v1 叫 `kg`）。表中 v1 动作取自 v1 的 README 与代码：`new-instruction` / `audit-instruction` / `new-report` / `audit-report` 四条 README 列过而代码里没有，前两条的意图由 `workflow create` / `workflow check` 承担，后两条退役。

| v1 动作 | 规格归属 | v2 动作 | 变化 |
| :-- | :-- | :-- | :-- |
| `workflow --new` | 工作流已创建；`POST /workspaces/{id}/workflows` | `workflow create` | 步骤带全局 `id`；写判据骨架 |
| `workflow <名字>` / `--list` | 读取单个 / 列出工作流 | `workflow show` / `workflow list` | 读路径不变 |
| （v1 无） | 定义核对（规格约束：路径在不在、小节有没有判据覆盖；不访问文件系统，由端侧判） | `workflow check` | 新增 |
| `workflow --export / --import [--as]` | 区间流转（显式导出或导入） | `workflow export` / `workflow import` | 撞名即拒、`--as` 换名，凭证不重发，与 v1 同 |
| `task --new` | 工单已创建；`POST /workspaces/{id}/workorders` | `order create` | 封面落笔即封；`id`、`workflow_id`、`created_at` 账本方查填，参数带了即拒 |
| `task <名字>` / `--list` | 读取工单全貌 / 列出工单（`?workflow_id=` 筛读） | `order show` / `order list` | 全貌 = 封面 + 全量流水；进度与完结由流水推导，不发结论字段 |
| `task <名字> --next` | 追加工作记录（`POST …/workorders/{name}/records`）+ 判据核对 | `order next` | 一步一条工作记录：`id` 追加方生成（幂等键）、`seq` 账本方分配、`step_id` 按 `step` 查填；agent 步骤交给智能体跑，程序核 `rule` 判据 |
| `task <名字> --done` | 同上（人记一笔） | `order done` | `is_succeeded` 来源与判据 `executor` 一一对应：`rule` 机械比对、`agent` 智能体审查、`human` 闸门放行；闸门放行落一条记录 |
| `task <名字> --journal` | 产物（日志类别） | `order journal` | 叙事落产物，不动流水 |
| （v1 无） | 工单不设 DELETE 于有账之单 | `order delete` | 新增：删一张白纸，流水非空即拒 |
| `find` / `catalog [--json]` / `audit [--make]` | 规格未规定 | 原样保留 | 实验室自留：工作区级动作 |
| `material [路径…]` | 材料；材料已收录 | `material` | 四字段不变（类型 / 内容 / 来源 / 时间），阶段由位置承担 |
| `new-instruction` | 工作流骨架 | 收编进 `workflow create` | 指令三段（目标 / 步骤 / 验收）由工作流加工单承担 |
| `audit-instruction` | 定义核对 | 收编进 `workflow check` | 判据跑在定义层 |
| `new-report` / `audit-report` | — | 退役 | v1 代码里并无此动作（README 列过、未实现），遂不移植 |
| `gui` / `kg-gui` | 无 | 退役 | 实验室不做窗口（代码与计划已撤） |

命令行取「名词 动词」——名词对资源，动词对方法（规格的端点表就是这么定的）。v1 的旗标写法也认（`order <名字> --next` 同 `order next <名字>`）——实验室自留。

## 数据

**账本归 CLI，内容归工作区**：CLI 自己维护的账本落 CLI 自己的数据目录（XDG），不写进工作区；产物是内容，落在工作区里。

```text
$XDG_DATA_HOME/qtcloud-work/           # 缺省 ~/.local/share/qtcloud-work
└── workspaces/<工作区键>/
    ├── workspace.yaml                 工作区身份：id / name / title / description / created_at / updated_at，缺则首跑生成
    ├── workflows/<工作流>.yaml        定义：name、description 与 steps；凭证按名派生，不落文件
    ├── workorders/<工单>.yaml         工单：封面加流水（records 内嵌，不另落盘）
    └── events.jsonl                   领域事件：WorkflowCreated / WorkOrderCreated / WorkRecorded，一条一行，只增不改
```

工作区里（人自己的地方）：

```text
artifacts/<类别>/<工单名>.md   报告与日志按类别分家，按工单名命名（--artifacts 可另指，如领域仓的草稿区）
```

`<工作区键>` 由工作区根的路径派生（可读名 + 短码）。位置不进模型，由启动参数装载：`--root` 工作区根（判据基准与扫描面）、`--data` 账本（缺省上面那处，指到仓库就等于入版控）、`--artifacts` 产物落点（缺省 `<工作区根>/artifacts`）、`--workflows` 定义目录（缺省 `<账本>/workflows/`，固定资产常另指一处）。

判据里用 `{{report}}` / `{{journal}}` 指产物落点——不写死名字，一份定义开多单也不串。
