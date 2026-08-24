# cabdecoding 技术路线分析（摘要）

> 对象：D:/training/cgns/cabdecoding（Cradle scSTREAM Pre 商业 CAE 格式+GUI 的逆向工程）。
> 用途：提取可复用于 Icepak 100% 对标的 (a) 网格 (b) 宏/向导 (c) ECAD 三条技术路线。

## 1. GUI 构建（可复用模式）

- PyQt5 + VTK：CabViewer(QMainWindow)；_build_ui 用 PaneFrame+QSplitter 四窗格（Tree/List + Control | Draw + Convergence(默认隐藏) + Message）；状态栏 5 段（coord/mode/op/target/group）。
- 菜单/工具栏：_build_menus（顶栏 8 菜单，未实现项走 _nyi 写 Message WARN）；_build_toolbars（5 条，ToolButtonTextUnderIcon）；部件工具栏由 cab_parts.PART_MENU_ITEMS 同步。
- 图标管线：cab_icons.AppIcons（QPainter 绘制+_cache[(name,size)]+_draw_{name} 分发+未知回退 _draw_generic）；cab_wizard_icons（nav_status_icon/bc_icon/purpose_icon/iwiz_atype_icon，lru_cache）。仓库不随包发布二进制图片。
- Headless：enable_3d=False 时 Draw 窗格退化为 QLabel，renderer=None——全链路可测试。
- i18n：cab_i18n（迷你 MVP：tr(key,lang)，ui_language 读设置）。

## 2. MESH 路线（核心可复用）

1. **格式容器**：.cab = Microsoft Cabinet + MSZIP + XML(cabxml.py) + Parasolid(parasolid.py)；cab_container.CabArchive 实现容器级解析与 to_bytes(preserve_source_blocks=True) **字节一致重建**（test_container::test_roundtrip_byte_identical）。
2. **探针驱动逆向**：stpre_probe.ProbeCase（案例矩阵：default/auto1_sweep/tr03_vd/ex4e_vd/stl_registration）-> run_case 构造 relay cab -> 启动 STpre_Bx64net.Application.2025 COM（ensure_open/grid/element/save）-> 解析输出刷新 records -> 数据落 data/stpre_probe_*.json -> analyze 做规则挖掘。
3. **静态逆向工具**（tools/）：search_dlls（定位编排函数）、strings_find（lief 提取 UTF-8/16）、xref（capstone RVA 交叉引用）、disasm_mesh（派发带分析）、pe_disasm（通用 x64 PE）、fetch_v35（参数文档）、mesh_create_probe（ctypes 结构体探测）、probe_cyl_domain/probe_stl_mesh/probe_tr03_marks。
4. **公式沉淀**：stpre_rules.py：auto1_per_axis_counts、geometric_first_spacing（g0=L*(1-q)/(1-q**n)，CalcFineCoord 0x1CB000）、geometric_coords、calc_ratio（CalcRatio1/2 0x1CB4F0/0x1CB840）、auto1_inner_count/split_outer_counts/outer_g0；_trunc_round=cvttsd2si(x+0.5)。
5. **GUI 网格六标签**：cab_dialogs.GriddingDialog（QTabWidget：Basic Setting/Parameter/Detail meshing/Edit/Deletion/Others）+ Gridding/Meshing/Close + Element-#（单元数=points-1）；基础页含 detection_radios（all/representative/axis_plane/minmax/not_considered/uniform）、method_radios（rough_only/rough_and_detail/num_elements）、domain_type_radios（cartesian/cylindrical/axial）、target_axes；参数页 ratio_common 三轴联动；编辑页 _edit_add/_edit_edit/_edit_delete（cab_grid.delete_grid_lines，B=受保护边界）；其它页 edge_eps/element_threshold/panel_block_face/check_scheme/part_mesh_option。
6. **网格算法**：cab_grid.py（GridSpec、build_axes L486、build_axes_multiblock L696、divide_interval L748、delete_grid_lines L808、parse_fine_divide/apply_fine_divide_to_model）；cab_mesh.py（classify_cells L740 区域占用射线投射、apply_elements、toggle_cells_effective（删角单元分 3 残块）、classify_interferences/find_interferences/resolve_interferences（按 part_priority_rank 裁剪）、find_flux_face_duplicates）；cab_domain.py（DomainSpec、apply_domain L115、fit_domain_to_parts L223）。
7. **显示/编辑**：cab_vtk.py：part_boxes、domain_frame、root_block_actor、element_division_lines（全结构体积线 L1020）、element_section_data/section_actor、mesh_block_display_actors（面网格+半透明 AABB 壳 depth 遮挡 L1565）、mesh_block_grid（stride 抽稀 L1508）；EditMeshDialog（Active block+I/J/K 层->Effective/Ineffective）；SectionDialog（Axis+滑块+fluid_only）；InterferenceDialog（Separation only+Reconstruct）。
8. **Golden 校验**：test_golden_reference.py 与官方 box_bm.s 逐点 atol=1e-15（CXYZ 每轴 55 点）、hdr1 行、occupancy [20,39,20,39,20,39] 钉死；test_tr03_probe_reference_counts_pinned；test_stpre_box_occupancy_golden（原生分类==STpre part_boxes）；test_mesh_params_algo（edge_eps=0.00015/element_threshold=0.9/face_search/worker 并行一致）。

## 3. 宏/向导路线

- **部件宏**：cab_parts.PART_MENU_ITEMS（27 项）+ PRIMITIVE_KINDS（含 ac_unit/diffuser/two_resistor/delphi/multi_resistor/heat_pipe/card_guide）；tess_for_part/tess_for_spec（从 XML 参数重算几何，不依赖 x_t）；register_primitive（写回 XML）；CreatePartDialog；m37 库部件 JSON 往返（set_project_value("part_library")）；m24/m31 mesh_boolean（subtract/intersect）+ flip 三角；m38 格式矩阵（OBJ/STL 往返、XT 需 pskernel、IGES/IDF 显式拒绝）。
- **热部件宏**：d7 热参数（peltier_current/delta_t/hot_face/heat_source/monitor；two_resistor 的 rjc/rjb/package_power）。
- **向导壳**：cab_wizards.WizardBase（DialogHeader+step_label+QStackedWidget+可选左导航 QTreeWidget；Back/Next/Finish/Cancel）；_add_page(key,title,widget,parent_key) 注册表；_mark_defined/_set_page_hidden/_fit_nav_width；InitialWizard 6 页（_IwProjectPage/_IwDomainPage/_IwAnalysisTypePage/_IwInitialGravityPage/_IwPurposePage/_IwConfirmPage）；ConditionWizard：_CW_PAGES ~50 页 + 导航树 + cab_cwizard_pages。
- **宏内核**：cab_stpre_api.STpreSession（COM）+ build_grid_params/build_block_params_from_gridspec/build_relay_cab/run_stpre_grid_mesh/merge_mesh_result —— 黑盒 oracle 驱动宏；GUI 开关 Option->Gridding/Meshing。

## 4. ECAD 路线

- **ECXML**（ecxml.py，~120 行核心）：Electronic Components XML，JEDEC two_resistor / Delphi / multi_resistor 紧凑热电路元件；schema：<ECXML version="1.0"><Component name kind manufacturer part_number><Location x y z unit="mm"/><Size x y z unit="mm"/><Thermal><Rjc/><Rjb/><Power/><Node name r/>...</Thermal></Component></ECXML>。函数：parse_ecxml、import_ecxml_path、register_ecxml_parts（-> cab_parts.register_primitive，参数 base/size/rjc/rjb/package_power/manufacturer/part_number/nodes，name_2 去重）、parts_to_ecxml（导出）。
- **映射进模型**：cab_gui._import_ifc_ecxml(path,ext)：.ifc -> cab_ifc.parse_ifc+register_ifc_parts；.ecxml -> parse+register；导入后 _mark_dirty -> populate -> _rebuild_scene。
- **输出**：xemt_export.build_emt（材料/部件映射，Version=2023，Material/Parts 块按属性库组序编号 _ordered_materials/_used_material_names）；s_export.build_sdat（SDAT/CXYZ/PARTS，@UNDEFINEDMOM、total-pres、source、尾部 GOGO+CRLF）。
- **保真测试**：test_sxemt_export（structural==0、CXYZ 仅末位浮点舍入差、consumed_by_flddecoding 交叉消费、xemt_material_numbers 行级对等）；test_import_assembly（装配展开 >=100 body、颜色循环 25,25,255,255 起、11 回 0）。

## 5. 方法论（可直接照搬）

1. 工作流：**probe(COM+DLL 反汇编) -> model(公式/结构) -> verify(与官方输出结构级对等) -> golden(参考 JSON/字节一致)**；test_workflow.py 端到端回归（解包->导入->域->网格规格+建轴->分类->应用单元->导出 S/XEMT->cab 往返保留）。
2. 字节级保真：CAB roundtrip 字节一致；S/XEMT 逐行比对（仅 CXYZ 末位舍入差）；CXYZ atol=1e-15；ps_facet2_nodes 复现 n=floor(L/std+2/3_f32) 浮点常量。
3. GUI 约定：零二进制图片（矢量图标）、headless 可测、naming 对齐官方手册、NYI 显式记录——三处均可平移到 icedecoding。