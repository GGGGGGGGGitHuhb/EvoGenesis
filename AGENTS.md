# AGENTS.md

## Loading Rules
- 先确认当前上下文是否已读取 `AGENTS.md`；若已读取且文件未变更，立即跳出本文件。
- 若 `AGENTS.md` 未读取、已被修改，或角色 guide 与本文件冲突，必须重新读取。
- 本文件优先级高于各角色 guide；角色 guide 只补充具体工作方式，不覆盖项目规则。

## Project
- 项目名称：EvoGenesis。
- 项目目标：构建一个命令行生物演化模拟器，按生命演化顺序逐步扩展，从 RNA World 开始，最终成为地球模拟器中的生命模块。
- 当前首版目标：模拟 RNA 序列复制、突变、资源竞争、降解、谱系兴衰、事件日志与快照恢复。
- 技术栈：Python 优先，使用标准库起步；后续如出现性能瓶颈，可将热点模块迁移到 C++。
- 开发环境：推荐 VS Code，配合 Python、Pylance、Ruff、Even Better TOML。
- 默认不引入重量级依赖；新增依赖必须说明必要性、替代方案和对项目复杂度的影响。
- 代码应保持清晰、可测试、可恢复运行；模拟规则要有明确生物学含义。
- 配置、状态、日志、快照、模拟规则应分层设计，不互相硬编码。
- 注释原则：说明“为什么这样建模/取舍”，避免解释显而易见的语句。
- Python 公共接口使用 docstring；若后续加入 C++ 模块，公共接口使用 Doxygen 风格注释。
- 格式化与 lint 以 Ruff 为准；提交前应通过必要测试与 smoke test。

## Required Reading

| 角色 | 必读文档 |
| --- | --- |
| Leader | `AGENTS.md`、`docs/leader/leader-guide.md` |
| Builder | `AGENTS.md`、`docs/builder/builder-guide.md` |
| Reviewer | `AGENTS.md`、`docs/reviewer/reviewer-guide.md` |

## Role Boundaries

| 角色 | 职责边界 |
| --- | --- |
| Leader | 负责任务拆分、阶段规划、范围收敛、架构与验收口径，不直接改代码 |
| Builder | 负责按 Stage 设计编码、测试、自查，不擅自扩大需求范围 |
| Reviewer | 负责最终审查、风险识别、回归测试建议，不替 Builder 实现功能 |