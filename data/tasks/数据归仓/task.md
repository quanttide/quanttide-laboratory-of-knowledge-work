# 任务：数据归仓

## 目标

所有数据放实验室 data/，禁止过滤。

## 步骤

- 改程序默认落点：数据写本仓 `data/`（`tasks/`、`report/`、`history/`）
- 写纪律：`AGENTS.md` 记下「所有数据放 data/」与「禁止过滤」
- 归档：判例搬进 `data/samples/`，散落的测试残留清掉

## 验收

- [ ] 机械：纪律写在案 `path:examples/default/AGENTS.md`
- [ ] 机械：判例在数据仓里 `path:examples/default/data/samples/report.md`
- [ ] 闸门：实验室外不再有程序写出来的数据
