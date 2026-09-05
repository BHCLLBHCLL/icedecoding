# P19-4 ~ P19-10 实施状态核对与开发计划

> 核对时间: P19-1/2/3/10 已实施后。核对方法与证据 = 代码 grep（ice_report/ice_macros/ice_gui/fluent_fdat/decoder）+ probe_work 指标 + 测试数。

## 一、状态核对（P19-4 ~ P19-10）

| 项 | 状态 | 已实现 | **未实现（缺口）** |
| --- | --- | --- | --- |
| **P19-4** 求解/后处理/报告 | **☑ 完成** | fdat 真实数据源；cas 面重建 cell→node（58,908 单元）；真实 VTK 温度云（12-1:124k 点）+ **iso/平面切/极值云按真实温着色**（蓝→红）；矢量 glyph（124k 箭头）；**真插值等值面**；**History / Network temperature / 3D Variation 真实曲线**；**Solve→Transient settings 接线**；**Post→Postprocessing units 接线**；**powermap 视区显示**；**Zoom-in 模型**；**Solve 面板字段全集（Patch/trials/ROM 字段表 golden 化 + Define trials/Create Krylov ROM 接线）**；报告 HTML 温度统计段+SVG + **Fan/网络块值/EM/Solar 段 + Overview 真实完整报告 + Autotherm 导出**（5 powermap 导出已在 D6d） | —（P19-4 收官） |
| **P19-5** 宏内置库 | **☑ 完成** | 动态三级注册扫描；向导壳；内置宏 5 个（heat_sink/bga/tec/sot/blower）；845 部件全量移植（参数化部件 + 每部件向导页 UI）；**oracle diff 校验**（tools/macro_diff.py：内置规则表 + 845 官方参数文件逐字回显/几何规则，delta=0；golden 锚定） | —（P19-5 收官） |
| **P19-6** ECAD 收官 | **☑ 完成** | ECXML/IDF/IDX/Networks/JEDEC/powermap 解析 + export_*；icb_metal_fractions；AEdt 脚本导出；**ODB++/ANF→ICB oracle 管线**（iceecad 广义 mode + GUI 导入）；**Show metal fractions 视区显示**（逐层铜箔 + 图例）；**Export AE 脚本 + 5 powermap 导出格式**（export_powermap 逆编码器，往返一致） | —（P19-6 收官） |
| **P19-7** 写回/Undo | **部分(~50%)** | model 编码器（encode_line/text，可逆）；Save/Save-as 链路；快照 Undo | **字节级往返**（fn 每行原始 seed + Il!! 模式——实测 encode 非字节一致）；全对象状态 Undo；脏标记细化 |
| **P19-8** IcBQS + CLI | **未实现(0%)** | 无 | IcBQS 批队列（6791 协议/状态机/任务属性）；批部署 CLI（启动/任务参数等价） |
| **P19-9** 语言包 | **部分(~40%)** | ice_i18n tr(key,lang) EN 恒等 + 自译 ZH（~78 行模块） | EN 完整表 + ZH 全键覆盖（当前仅覆盖已用标签）；三态切换测试；@UI 字符串全部走 tr() |
| **P19-10** 真实 cas/fdat | **☑ 完成** | fdat 字段解析（float64 LE/125 区/SV_T 295-305K）；cas 面重建；真实温度云；直方图；报告段；全作业覆盖调查（12-1 97%） | 可选：流体全温度区（部分作业未初始化已实证）；云图/曲线/报告渲染衔接 |

**结论**：P19-10 ✅ 完成；P19-4/5/6/7/9 **部分**；**P19-8 完全未实现**。缺口中最硬的三块 = P19-4 的 3D 标量/矢量视区渲染、P19-7 的字节级编码器、P19-8 的 IcBQS。

## 二、开发计划（按优先级 × 难度排序）

**Phase A — P19-4 后处理真实渲染（价值最高、与已交付真实数据源直接衔接）**
1. 标量场视区渲染：**iso 面**（vtkContourFilter 按温度等值）+ **平面切**（vtkPlane + 着色）+ **探针点/极值**（真实温度），接入 `_post_display` 与 `_create_post`；验收：等值面/切面着色与真实温度吻合（对照 12-1 云图范围）。
2. **矢量场**：fdat SV_U/V/W → vtkGlyph3D 箭头；验收：流速场箭头方向/大小一致。
3. **6 曲线**（convergence/variation/history/trials/3D-variation/网络温度）全部接真实 fdat（read_fdat_residual/history + real temp）；trial 从 `trials_from_problem`。
4. **Solve 面板字段全集**（Basic/Advanced/Parallel/Patch/trials/ROM 字段表，golden 化）；验收字段 100% 对表。
5. **报告全套**：Summary/Point/Full/Overview + 网络块值/Fan 工作点/EM/Solar/Autotherm + 5 导出（数据源=fdat + model + post_objects）；验收与官方 summary 数值一致（10-1/12-1）。

**Phase B — P19-7 字节级写回（数据层收尾）**
6. 还原每行原始 seed 与 Il!! 模式（decode→记录每行 magic/seed→encode 用原始 seed），字节级往返；验收 10-1/5-1fin/8-2 model 往返 == 原文件。
7. 全对象状态 Undo/Redo（对象列表快照含 setvals/shape）+ 脏标记+关闭提示；验收 连续编辑→撤销→重做→保存一致。

**Phase C — P19-8 IcBQS + CLI（外围）**
8. IcBQS 协议客户端（端口 6791，任务提交/状态/结果）+ 自实现调度（多作业串行）；验收协议文本对照 golden。
9. 批部署 CLI（`python -m icepak_cli run job --solve --report`）；验收 CLI 等价 GUI 产出。

**Phase D — P19-6 ECAD + P19-5 宏 + P19-9 语言（业务/外围收尾）**
10. ECAD：ODB++/ANF→ICB oracle 管线（iceecad 沙箱）；AEdt 脚本导出；Show metal fractions 视区显示；剩余 5 导出格式；验收与 oracle 同输入产物比对。
11. 宏：官方 icelib/macros 全量移植（每宏参数化部件+向导页）；验收每宏产物与官方 diff=0。
12. 语言：EN 全键表 + ZH 全键覆盖（键=language_text_* 键名），全部 UI 字符串走 tr()；验收全键覆盖率 100% + 三态切换测试。

## 三、工作量与排期（估计）

- Phase A：~4 项（后处理渲染 + 曲面 + 求解面板 + 报告），重点 1-2 周；
- Phase B：~2 项（字节级编码器 + Undo），1 周；
- Phase C：~2 项（IcBQS + CLI），1 周；
- Phase D：~3 项（ECAD 收官 + 宏库 + 语言），1.5 周。
- 总计 ~4.5-5.5 周，按 A→B→C→D 顺序（A 与已交付真实数据源衔接，B/C 数据层/外围，D 业务收尾）。
