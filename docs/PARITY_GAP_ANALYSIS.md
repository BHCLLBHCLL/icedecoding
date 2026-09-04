# Icepak 19.5 100% 对标：当前覆盖度/深度分析与下一步开发项清单

> 生成: 2026-08（P0–P18j 全部落盘之后）
> 对标对象: ANSYS Icepak 19.5（icepak.exe + mesher/hdm + ecxml/iceecad + IcBQS）
> 依据: docs/ICEPAK_UI_100PCT_PLAN.md、docs/icepak_gui_golden.json（11 菜单/9 工具栏/79 热键/70 图标键）、REVERSE_STATUS.md P0-P18j、194 项测试、tools/probe_work/* 取证档案

---

## 一、总体进度：三大层面各自走到哪

| 层面 | 完成度评估 | 关键证据 |
| --- | --- | --- |
| **UI 契约（菜单/工具栏/热键/树/表单）** | ~85% 骨架 + ~60% 行为 | golden 驱动 11 菜单/9 工具栏/79 热键 1:1；树组织/表单引擎/编辑器/对齐会话/宏/ECAD/偏好/i18n 已落地；差距集中在视区视觉全集与逐类字段 |
| **数据格式（解析/编码）** | ~90% | model 混淆解码（26 工程 1200+ 对象零未知）、tzr、problem、grid_params、post_objects、cas 区计数（hex）、nodemap、**二进制 grid_output 28B BE 节点记录**；编码器/ECXML/IDF/IDX/Networks/JEDEC/powermap/ICB 已有 |
| **网格/求解复刻（深度）** | 计数 100%、位置谱 ±4~8% | 16 工程节点计数 **0 误差**（P17）；位置谱 x −8.1% / y +4.6%（P18h 环模型）；自研 heat_solver 验证 ≤5% |

**里程碑**：P0-P9（UI 骨架→树→视区→表单→网格→求解→宏→ECAD→偏好）全部验收；P10 真实工程回归；P11-P12 oracle 取证基础设施（binary 分析器 + cas/nodemap golden）；P13-P15 网格复刻（保形加密→自适应→交叉扫描）；P16 连续细分 + **hex 区计数修正**；P17 **节点计数 0 误差**（hanging-node 板片）；P18-P18j 位置级 1:1 攻坚（HDM 八叉树 → 基尺寸/曲面投影/曲率判据/局部容差/均匀环/相位/重叠机制 → 晶格派生采样定案）。

## 二、分层覆盖度矩阵（现状）

深度评级：**D5** 字节级/golden 对标 · **D4** oracle 定量对标 · **D3** 功能完整+测试 · **D2** 可用但浅 · **D1** 骨架/NYI

| 子系统 | 模块 | 现状 | 深度 | 100% 差距 |
| --- | --- | --- | --- | --- |
| model 解码 | icepak_parser | 完整（混淆公式、shape/setval、post 引用） | D5 | 无 |
| model 编码/写回 | ice_create + editors | 可写（序列化+编码器），Save/Save-as 链路 | D3 | 字节级往返验收 + Undo 全集 + 脏标记细化 |
| problem | icepak_parser | 只读解析 + setter 读写 | D3 | 数组类字段（gradient/transient 表）全解析 |
| grid_params | ice_mesh | 读写 + per-face 尺寸取证 | D4 | 无（已用 oracle 交叉验证） |
| grid_output 二进制 | fluent_grid + tools/grid_positions | 28B BE [counter][x][y][z] 节点区 + cas hex 区计数 | D5 | face/cell 区（32B 记录）完整解码 |
| cas/fdat/resd | fluent_grid + ice_solve | cas 区头/区计数；resd 读写；fdat 未 | D3 | fdat 全解析（后处理数据源） |
| 菜单/工具栏/热键 | ice_actions + ice_menus_toolbars | golden 驱动 1:1（11/9/79） | D4 | Windows 动态菜单细化；File WB 变体；多命令按钮 |
| 主窗口/树 | ice_gui + ice_panes | 9 大组件；Project/Library 树；组织/排序/右键/拖放；Find；Spreadsheet；Edit toolbars；欢迎流 | D3 | 树图标按键对齐；组右键全集补漏 |
| 3D 视区 | ice_view3d + ice_gui | 7 形状/5 着色/拾取/对齐会话/box+circle 拾取/snap/2-4 窗/测量/标记/网格线 actor | D3 | **视觉契约全集**（Lights、背景样式、per-type 颜色/线宽/透明度、user views 文件、面/边循环选择、拖放移动、栅格可视化、深度提示、右下实时坐标） |
| 对象编辑器 | ice_editors + ice_forms | Form/Notebook 引擎；Info/Properties/Geometry 通用三页；CopyFrom | D2 | **18 类逐类字段全集**（golden 字段表驱动）；多体编辑；右下几何信息窗橙色按钮 |
| 网格 | ice_mesh + ice_refine + ice_hdm | AutoHex 六页签；生成管线；复刻引擎（保形/自适应/连续细分/HDM） | D4 | 真实 mesher 沙箱对接；质量统计面板；优先级/挖空面板 |
| 求解 | ice_solve(_gui) + heat_solver | 设置面板；运行+残差监控；自研稳态导热求解器 | D2 | Basic/Advanced/Parallel 字段全集；Patch；trials/report；ROM/优化；IcBQS 队列 UI；solution ID |
| 后处理 | ice_solve + ice_gui | post 对象创建；平面切/等值/采样点/对象温度；**iso/平面切/极值云按实温着色（蓝→红）**；矢量 glyph（124k 箭头） | D3 | 真插值等值面（vtkContourFilter 三角面）；6 种曲线；瞬态设置；单位；zoom-in；powermap 显示 |
| 报告 | ice_report | HTML 报告 | D2 | Summary/Point/Full/Overview；网络块值/Fan 工作点/EM/Solar；Autotherm；5 导出格式 |
| 宏 | ice_macros(_gui) | 动态三级注册；向导壳；内置宏参数化 | D2 | 内置宏库全量移植（部件宏+向导页，oracle=官方宏产物 diff） |
| ECAD | ice_ecad | ECXML/IDF/IDX/Networks/JEDEC/powermap 解析+导出/ICB 解析/EM mapping/metal fractions/**ODB++/ANF→ICB oracle 管线**/AEdt 导出/**Show metal fractions 视区显示**/**Export AE+5 powermap 导出** | D4 | —（ECAD 收官） |
| 偏好/语言 | ice_prefs(_gui) + ice_i18n | Preferences 页签；en/zh 词典 | D3 | ~/.icepak_config 变量级兼容导入导出；Annotations |
| 周边 | — | Python console 等价；图像导出；批部署 CLI | D2 | IcBQS 批队列协议；Command prompt 全命令 |
| HDM 位置复刻 | ice_hdm | 八叉树+尺寸场+曲面投影+曲率判据+局部容差+均匀环；相位/重叠机制定案 | D4 | **晶格量化表面节点**（最后一块，见下） |

## 三、与 Icepak 的关键差距（按对"100% 对标"的影响排序）

1. **位置级 1:1 最后一公里**：节点计数已 0 误差；位置谱 x −8.1% / y +4.6%。P18j 定案：oracle 表面节点为**晶格派生采样**（同列柱 x 集 27-41% 部分重叠，自由相位环无法产生部分重叠）。→ 唯一剩余机理项。
2. **3D 视区视觉契约全集**（tdv 功能清单 §1.8 的剩余项）：Lights、背景样式、per-type 属性、user views 持久化、面/边循环选择、对象拖放移动、snap 栅格可视化、实时坐标。
3. **对象编辑器逐类字段**：18 类对象 × Info/Properties/Geometry 的逐类字段布局（golden 字段表尚需按类固化）。
4. **求解/后处理/报告链路深度**：真实 mesher/solver 数据打通（cas/fdat 读、云图、6 曲线、5 类报告）。
5. **宏内置库全量移植**（官方 icelib/macros 三级库 → 参数化部件宏+向导）。
6. **ECAD 收官**：ODB++/ANF→ICB oracle 管线、AEdt 导出、Show metal fractions 视区显示、Export AE 脚本+5 powermap 导出格式（全部已交付）——P19-6 收官。
7. **写回与 Undo**：model 编码器字节级往返 + 全对象状态 Undo。
8. **IcBQS 批队列**（端口 6791 协议）+ 批部署 CLI。
9. **语言包**：EN 完整表 + ZH 自译收尾。

## 四、下一步开发项（P19，按优先级）

**P19-1 晶格量化表面节点（HDM 位置复刻收官）**
- 目标：10-1 位置谱 x/y 进入 ±3~5%，比值 1.15-1.25，1e-3 重合率 >10%。
- 做法：全局细晶格（0.02/2^k，k=壳深度）采样柱面邻域点 → 投影锥面 → 量化回晶格；晶格相位=当前 best (0,0.008)；调 k 与量化步长使同列柱 x 集重叠率≈30-40%（oracle 实测）。
- 验收：x/y 偏差与重叠率双达标；golden 化 10-1 指标。

**P19-2 3D 视区视觉契约全集**
- Lights 面板（多光源/强度/位置）；背景纯色/双色切换+颜色设定；per-type 颜色/线宽/着色/装饰；逐对象透明度；user views 保存/清除/文件；面/边循环选择（红/黄高亮、中键接受）；对象拖放移动（Interaction 规则）；Visible grid/Origin/Rulers/Title/Date/Construction/Depthcue 视觉落地；右下实时坐标与状态栏 4 段。
- 验收：对照教程图 3-31/3-62/3-65 截图回归（_report/screenshots）。

**P19-3 对象编辑器逐类字段全集**
- 18 类对象的 Info/Properties/Geometry 字段表（golden JSON：类→页签→字段/控件/默认值/单位）；spreadsheet 多体编辑；右下几何信息窗橙色对齐按钮族。
- 验收：字段与 params 表 100% 对表；test_editors_fields golden 测试。

**P19-4 求解/后处理/报告全链路**
- ~~Solve 面板字段全集（Basic/Advanced/Parallel/Patch/Trials/ROM）~~ **已交付**（PATCH/TRIALS/ROM 字段表 golden 化 + Define trials/Create Krylov ROM 接线）；批队列 UI（IcBQS 语义，Phase C 已做）；post 视区云图/矢量/等值面/探针/极值（已全部真实化/着色）；+ 瞬态设置（已接线）+ 单位（已接线）+ Zoom-in 模型（已做）；报告 Summary/Point/Full/Overview + 网络块值/Fan 工作点/EM/Solar/Autotherm（已全部加段）+ 5 powermap 导出（已做）——**P19-4 收官**。
- 验收：面板字段对表；后处理与 heat_solver 数据打通（结构化网格先，HDM 网格后）；报告 golden 样例。

**P19-5 宏内置库全量移植**
- 官方 icelib/macros 三级宏 → 参数化部件宏+向导页；每个宏：参数/几何与官方宏产物模型文件 delta=0（oracle 沙箱）。
- 验收：宏清单对表；产物 diff golden。

**P19-6 ECAD 收官**
- ODB++/ANF→ICB oracle 管线（iceecad.exe 沙箱，已交付：广义 `convert_ecad_to_icb` mode 表 + GUI 导入）；AEdt 脚本导出（已交付）；Show metal fractions 视区显示（已交付）；**Export AE 脚本 + 5 powermap 导出格式收尾**（`export_powermap` 逆编码器 + File/Report 槽位）——P19-6 收官。
- 验收：与 oracle 同一输入的产物比对。

**P19-7 写回与 Undo**
- model 编码器字节级往返验收（往返==原文件）；全对象状态 Undo/Redo；Save/Save-as 全链路 + 脏标记提示。
- 验收：字节级测试 + 编辑→保存→重载一致。

**P19-8 批队列 + CLI**
- IcBQS 协议（6791）客户端/自实现调度；批部署 CLI（启动/任务参数等价）。
- 验收：协议文本对照 golden。

**P19-9 语言包收尾**
- EN 完整表 + ZH 自译全键覆盖（键=原版 language_text_* 键名）；三态切换测试。
- 验收：全键覆盖率 100%。

**P19-10 真实数据打通（后处理数据源）**
- cas/fdat/resd 全解析（fdat 区/面数据）；把真实求解结果接入后处理与报告（替代合成数据）。
- 验收：10-1 真实 fdat 的云图/曲线与官方 summary 数值一致。

## 五、测试与验收体系（现状）

- 194 项测试全绿（22 个测试文件；headless offscreen + 真实桌面 GL 回归）。
- golden 资产：docs/icepak_gui_golden.json、tools/probe_work/*（oracle_report / fine_batch / fine_exact / hdm_* / pos_* / 16 工程指标档案）。
- 回归：tools/regression_3d_real.py（真实工程桌面回归）+ _report/3d_regression_summary.json + 截图。
- 方法论：probe→model→verify→golden（网格/格式线）；GUI 同构+headless（UI 线）；参数化部件宏+向导（宏线）。

## 六、结论

对标 100% 的剩余工作约 **10 个开发项**，其中 P19-1（晶格量化表面节点）是唯一尚未破解的**机理级**问题，P19-2/P19-3 是体量最大的**UI 契约**补全，P19-4/P19-6/P19-8 是**业务链路**深度。数据层与网格复刻层已实质达到或超过规划预期（节点计数 0 误差为全项目最高成就）。
