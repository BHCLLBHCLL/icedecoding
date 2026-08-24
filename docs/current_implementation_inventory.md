# 当前实现清单（审计摘要）

> 审计范围：D:/training/caedecoder/icedecoding 全部源码与测试（只读审计）。
> 结论一句话：现有实现是 **"Icepak 2019 R3 同构的只读查看器 + 轻量内存编辑"**——骨架（菜单/工具栏/双树/视口/消息）与查看闭环（着色/Orient/拾取/显隐/分组/Undo/导出/打包）基本完成，解析链路 26 项目全通过；但求解/网格/辐射/后处理/报告/宏/ECAD 导入/真实对象编辑/写回均为 NYI。

## 1. 技术栈

| 层 | 选型 | 相关类 |
|---|---|---|
| GUI | PyQt5 | IceGui(QMainWindow)、QApplication、QDialog |
| 3D | VTK 9.3.1 | QVTKRenderWindowInteractor + vtkRenderer；numpy->vtkPolyData |
| 树 | QTreeWidget | ProjectTree、LibraryTree（QTabWidget 双页） |
| 图标 | QPainter 矢量 | IceIcons.get(name,size)，缓存 _cache |
| 日志 | QPlainTextEdit | MessageWindow（Verbose/Log/Save） |
| 抽象 | HAS_GUI / enable_3d=False | headless 模式（无 VTK 也可构建 UI） |

## 2. 已有功能（均已确认）

- **主窗口**：标题 ANSYS Icepak 2019 R3（打开后加项目名）；1600x900；左侧 nav_tabs(Project/Library) | 右侧垂直 splitter（Graphics 上 / MessageWindow 下 5:1）；Graphics 内 TdvStrip(32px) + QStackedWidget（单窗/四分 QLabel）；状态栏 -> 3 段（项目名/Mode/No project）。
- **菜单 11 个**：与 menus_icepak.tcl 黄金规格 1:1（File/Edit/View/Orient/Macros/Model/Solve/Post/Report/Windows/Help 全部级联项、热键文本、Workbench 差异项均有）；File 的全套 Import/Export/EM Mapping 子菜单在。
- **工具栏 9 组三行**：行1 File(cmd5)/Edit(Undo+Redo)/Viewing options(7)/Orientation(5)；行2 Model and solve(6)/Postprocessing(12)；行3 Object creation(18)/Object modification(4)/Alignment(7，全 _nyi)。图标 24px ToolButtonIconOnly。
- **热键**：全部应用级注册（Ctrl-N/O/S/P/Z/R/X/C/W/A/V/H/E/T/M/L、Delete、F1、Shift-?）+ 视区 h/z/s/Shift-X/Y/Z/R/I。
- **对话框**：WelcomeDialog(Existing/New/Unpack/Quit)；DetailsTable+DetailsDialog（通用只读 [Property,Value]）；TranslateDialog(dx/dy/dz)；TdvStrip(pick/boxpick/rotate/pan/zoom+hide)；find_icepak_lib()。
- **3D**：渐变背景 #9ec8e8->#f4f7fb；ParallelProjectionOn+TrackballCamera；左下 vtkAxesActor 三联；右上 ANSYS 2019 R3 水印(0.55)；7 种几何（hexa/quad/cyl(空心)/polygon/container/circ/None）；KIND_COLORS 20 类（domain 恒线框绿）；5 种着色 SHADING_MODES；vtkPropPicker 拾取->变红高亮；双击->对象对话框；对象名 3 态（BillboardTextActor3D/CaptionActor2D）；Orient 全套（Home/Iso/±X±Y±Z/Zoom/Fit/Reverse/Nearest）；1/4 分屏（多 renderer viewport）。
- **模型树**：根=工程名；Problem setup(Basic parameters/Title-notes/Parameters and trials/Local coords)、Solution settings(Basic/Advanced/Parallel)、Groups、Post-processing、Points、Surfaces、Trash、Inactive、Model(Cabinet+kind(count) 分组，每对象带 visible 勾选)。Library 只读浏览。
- **能力**：26 工程（17 目录 + 9 .tzr）解析全通过；1247 对象 1195 可几何化；model 解码算法 v = c - KQ[i%7] - KC[i%16] - seed 可逆（decoder.py encode 已备）；tzr pack/unpack；Pack/Unpack 菜单走 tzr；Export CSV/Excel 走 export.py；18 类对象内存创建/移动/复制/删除/显隐/分组/Undo 快照。

## 3. 主要差距（详见 ICEPAK_UI_100PCT_PLAN.md §2）

1. **求解/网格/物理**：Generate mesh、Run solution、Run optimization、Krylov ROM、Solution monitor、Patch、trials/report、Radiation form factors、Edit priorities/cutouts、Create material library、Power and temperature limits 全部 NYI。
2. **真实对象编辑**：无分类型 Object 编辑器（只有只读 DetailsDialog）；无几何/参数/材料编辑；Save/Save as 不写回；Undo 仅 model 文本快照。
3. **导入导出**：IDF/IDX/ECXML/Powermaps/Networks/JEDEC/EM Mapping/ANSYS AEDT 脚本/Autotherm/Cadence/SIwave/Sentinel/RedHawk 全 NYI；仅 CSV/Excel + .tzr。
4. **树/导航**：Points/Surfaces 空；无排序/组织切换；无组节点右键；无 Remove from group/spreadsheet/拖放；Find 仅对象名。
5. **3D**：无网格 actor；Visible grid/Origin/Rulers/Title/Date/Construction/Depthcue/Mouse position 仅 checkable 无视觉；无 2 窗；无 boxpick 多选/circlepick/Blank/Unblank；无面边选择；无对齐匹配；无 Lights；无背景样式切换；无 per-type 显示属性；无透明度；无拖动；无 user views；无 markers/rubber bands/traces；无测量；无 Tcl console。
6. **宏**：静态 7 条硬编码（ATX/Micro-ATX chassis、Angled Fin Heat Sink、PCB、Polygonal ducts、Heat sink creation、Detailed heat sink creation、Heat Pipe）；应动态扫描 icepak_lib/macros 三级注册。
7. **后处理/报告**：全 NYI（只有 Load/Save post objects 文本）。
8. **其它**：Preferences/Annotations/clipboard 无；消息无红级；Windows 菜单非动态；图标为矢量重绘非官方 PNG/XBM（按策略允许）；解析器多边形顶点/grid_params 结构化/problem 数组/ECXML 未解码。

## 4. 致谢：审计用到的关键代码位置

- ice_gui.py：_build_ui/_build_menus/_build_toolbars/_set_shading/_apply_orient_to_camera/_set_view_panes/_on_release/_add_name_labels
- ice_panes.py：WelcomeDialog/DetailsTable/DetailsDialog/TranslateDialog/ProjectTree/LibraryTree/TdvStrip
- ice_create.py：default_object/HEXA_KINDS/QUAD_KINDS/CYL_KINDS/default_cabinet/serialize_model/project_files_for_pack
- icepak_parser：decoder.py/tzr.py/model_parser.py/problem_parser.py/project.py/export.py/cli.py
- tests：test_gui/test_create/test_tzr