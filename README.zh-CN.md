# 罕见病遗传咨询技能

[English](README.md) | 简体中文

这是一组可安装到 AI Agent 中的技能，用于以人工复核为中心的罕见病体质性与
生殖系遗传咨询工作流。它面向支持技能或插件的图形界面 Agent 软件，例如
Codex、Claude Cowork 和 WorkBuddy。它可以帮助整理中文或英文病例叙述、审核
变异表和已注释变异集、排序候选疾病、解读序列变异与拷贝数变异（CNV）、检索
文献、分析阴性或意义未明结果、绘制家系图，以及起草遗传咨询摘要。

> [!IMPORTANT]
> 这些技能用于临床决策支持，不能自主作出诊断。变异分类、候选疾病排序、报告
> 和建议均为需要合格遗传学专业人员复核的提案。请勿将其用于急诊、肿瘤体细胞
> 分析、药物基因组学或独立制定治疗方案。

## 请 AI Agent 帮你安装

不需要编程知识，也不需要使用命令行。在支持技能或插件的图形界面 AI Agent
中，直接发送以下消息：

> 请从 <https://github.com/muwenbo/genetic-counseling-skills> 为当前 Agent
> 安装并配置 **Rare Disease Genetic Counseling** 技能。请使用本应用支持的
> 安装方式。完成后请告诉我这些技能是否已可用、需要哪些权限或网络访问，以及
> 是否需要重启应用或开始新会话。

Agent 应负责完成适用于当前软件的配置，并在下载依赖项或进行涉及安全的更改前
征得你的同意。

## 包含的工作流

- 整理结构化罕见病病例，并提出可供复核的 HPO 映射。
- 检查并规范化实验室变异表，不将原表中的注释视为已经独立验证的事实。
- 按复核者确认的字段和阈值筛选大型本地已注释生殖系变异集。
- 对仅基于表型或结合变异信息的候选疾病进行排序，同时保留覆盖缺口和冲突证据。
- 构建可供复核的 ACMG/AMP、ClinGen VCEP 及体质性 CNV 分类提案。
- 检索变异和基因—疾病相关文献，并提取支持具体主张的证据。
- 解释阴性或意义未明变异（VUS）结果、检测盲区及审慎的后续检测假设。
- 起草面向临床人员的遗传咨询摘要，并可选择生成患者友好版本。
- 根据用户提供的家族信息创建经过验证的家系数据和可供复核的家系图。

这些技能不连接临床病历系统，也不会向其中写入结果。临床叙述和本地文件默认保留
在本地。需要使用科学服务时，工作流会尽量减少对外发送的数据，并记录服务名称、
操作、版本、警告和失败信息。

## 开发者设置

克隆仓库后，初始化已锁定版本的上游依赖：

```bash
git submodule update --init --recursive
```

开发环境使用锁定的 Git 子模块进行序列注释和 VCEP 查询。全新安装后，经用户明确
同意，技能可以获取同一份不可变、采用 MIT 许可证的提交，验证后存入不含临床数据
的本地缓存。该设置请求不会包含病例或变异数据。

知识图谱技能使用 `https://rdkg.viknox.com.cn`。中文或中英混合的临床发现会先在
本地翻译为经过语义核对的精简英文短语，再用于 HPO 检索；原始病例叙述和身份标识
不会被发送。

## 架构与验证

- `docs/architecture.md` — 组件边界与集成策略
- `docs/skill-contracts.md` — 十项工作流的用户侧契约
- `docs/rest-api-contracts.md` — 技能调用的 REST 接口契约
- `plugins/rare-disease-genetic-counseling/schemas/` — 共用的复核与来源记录模式
- `evals/manifest.json` — 独立验收用例

仓库检查方法见 [AGENTS.md](AGENTS.md)。最小的验收用例完整性检查为：

```bash
python3 evals/check_fixtures.py
```

仓库许可证见 [LICENSE](LICENSE)。随附家系图资源保留的第三方许可证见
[第三方声明](plugins/rare-disease-genetic-counseling/skills/draw-pedigree/assets/THIRD_PARTY_NOTICES.md)。
