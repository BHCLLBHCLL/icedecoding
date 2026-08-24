# Icepak 19.5 GUI 逆向规格书（证据与架构）

> 逆向对象：C:/Program Files/ANSYS Inc/v195/Icepak/icepak19.5（launcher: bin/icepak19.5win64.bat -> bin.win64_amd/icepak.exe）。
> 本文档 = 框架/机制级逆向结论（行号出处齐备）；菜单/工具栏/热键的机器可读规格见 docs/icepak_gui_golden.json；布局/行为描述见 ICEPAK_UI_100PCT_PLAN.md。

## 0. 二进制/源码证据链

| 资产 | 结论 | 证据 |
|---|---|---|
| icepak.exe | Tk 8.1 for Windows（Wish Application，原名 icepak81.exe，Scriptics） | VersionInfo：ProductName/OriginalFilename/FileDescription |
| 3D 引擎 | tdv（The Data Viewer）OpenGL 原生扩展，内嵌 exe | 字符串 Tdv_Viewer/tdv_image/tdv_geo/tdv_axes/tdv_begin_op/tdv_end_op/tdv_pickable_tags/OpenGL supported |
| 命令框架 | guibase Tcl 层（menu/toolbar/command/form/toplevel/configfile/scontrol 模块）+ 编译 digest | lib/guibase/guibase.tcl/commands.tcl/settings.tcl；lib/guibase|icepak|autohex 的 digest |
| 树 | BWidget 1.3.1 ::Tree | guibase.tcl:318 package require -exact BWidget 1.3.1；lib/bwidget/tree.tcl |
| 编辑器 | Fluent 系 form 机制 + notebook + Tktable | object_edit_use_notebook=1（init:195）；tkTable.tcl；form_init 等（init:865+） |
| 语言 | EN/中文(EUC-CN)/日文(SJIS) 三套 | language_text_prefix（init:331）；文件编码（GB18030/SJIS） |
| 偏好 | ~/.icepak_config / .icepak_defaults / .icepak_qnodes（Tcl 脚本，可 source） | init:621-623；autohex.tcl:473-476/527-530 |
| ECAD | iceecad.exe（EDB/ANF/ODB++/IPC2581->ICB）；ecxml.exe（EC XML）；NETEX-G64（Qt5 ODB++ 前端） | extension/lib/NETEX-G64 目录；strings |
| 网格 | AutoHex（whoami=AutoHex）/ ICEM AutoModel + bin.win64_amd mesher 群 | autohex.tcl:16-46；params_auto.tcl 全表 |

## 1. 主窗口创建链（guibase.tcl）

- guibase.tcl:749-756：top_setup -> special_make_main_window 或 make_main_window $viewer_win_orient（默认 v）-> make_message_window -> make_tool_windows -> adjust_window_geometry。
- 单窗口：ICEPAK_ONE_WINDOW=1（init:12）+ if !$toplevel(single) top_withdraw .（:770）；.v 与其它 toplevel 以 Map/Unmap + withdraw_toplevels 联动（791-792）。
- 视口：tdv_default = .v.view（guibase.tcl:93）；pickable tags：obtype_all anno_pickable post_pickable（init:688）。
- 删除协议：Use the Done or Quit commands to dismiss the form or exit the program.（guibase.tcl:760-768）。
- 几何：topform_geo +0+[winfo rooty $tdv_default]；botform_geo -0-0（781-783）。

## 2. 命令注册/菜单/工具栏机制（commands.tcl）

- command_define {longname shortname icon cmd bubble helpurl whenactive ?dragoff_cmd?}（commands.tcl:16-44）；全局 command(all-commands/all-menus/all-toolbars/hotkeys)。
- command_set_text / command_set_icon / command_set_tree_icon / command_set_hotkeys / command_set_hotkeys_tdv（本地化、图标、树图标、热键）。
- command_make_menu {longname active side entries args}：active=always 常显；not_present 跳过；side=left 或 {left set_path <glovar>}（Windows 菜单：menus_icepak.tcl:505）或 {left button}；entries=分离器/{name act type ...}/cascade/variable_cascade/radiobutton/checkbutton；args={keyboard f}/{notearoff}；两阶段创建（command_create_menus :301、command_create_one_menu :317、menubutton+underline 热键 :369-379）。
- command_make_toolbar {longname rownum entries {at_end 1}}：rownum=1 主区第 1 行；1 object_tools（两元素列表）＝对象工具区（Object creation/Object modification/Alignment 落此区，仅非 -viewer 且 !no_object_creation_toolbar 时出现，commands_icepak.tcl:473-476）；entries 支持 cascade/multiple/menu；at_end 0=前插；__space__=行间隔（command_make_toolbar_space :144）。
- 按钮元组 {shortname icon cmd whenactive bubble url dragoff}（command_create_toolbars_ent :204-218）；气泡含 Key = ...。
- Edit toolbars = 由 command(all-toolbars) 生成开关对话框。

## 3. 3D/tdv 命令全集（commands_guibase.tcl:1-172，均作用于 current 视口）

- 视图：tdv_home/tdv_zoomin/tdv_scale_to_fit/tdv_rotate_screen_y/tdv_rotate_screen_z/tdv_reverse/tdv_nearest_axis/tdv_isoview；tdv_along_axis current ±x/±y/±z；tdv_save_current_orientation/tdv_clear_user_views/tdv_save_user_views/tdv_load_user_views；tdv_print_shortcuts。
- 显示开关：tdv_toggle_track_mouse/tdv_toggle_depthcue/tdv_toggle_axes/tdv_toggle_two_d_grid/tdv_toggle_origin/tdv_toggle_rulers/tdv_toggle_title/tdv_toggle_display_logo/tdv_toggle_date（均 all）。
- 测量：tdv_check_angle/check_location/tdv_check_bbox/tdv_check_unit_vector/tdv_check_unit_normal。
- 灯光：tdv_lights_edit；鼠标：tdv_edit_bindings；背景：Set background；分屏 view_panes(mode)（1/2/4，toggle_view_split_mode，autohex commands_autohex.tcl:367-377）。
- tdv 热键集：menus_icepak.tcl:151-166（h/z/s/Shift-X/Y/Z/R/I/Shift-?/F5-F9）。

## 4. 树命令集与树行为

- 树命令：tree_edit_current_selection/tree_delete_selected/tree_toggle_current_active|visible|shading/tree_open_close_current（{} model 1 指定 Model 树窗）/tree_update_type_visible/tree_remove_from_group_action/tree_spreadsheet/tree_find_form/tree_show_clipboard/tree_clear_clipboard/tree_search_library/tree_make_library_subtree（init:414；commands_icepak.tcl:390；commands_autohex.tcl:392-438）。
- 组织层次：tree(detail) 0..3（flat/types/types+subtypes/types+subtypes+shapes，commands_autohex.tcl:672-686）；排序 L660-670；job_listsort（creation_order 默认，problem 变量）。
- 每类型可见：type_visible($type) 复选（commands_icepak.tcl:443-470；View->Visible 级联）。
- object_type_title 键序（语言文件）：domain(Cabinet)/block(Blocks)/ventres(Grille)/enclosure/heatsink/network/heat_exchanger/opening/periodic/source/pcb/plate/wall/fan/resistance/package/material/blower/pipe/Highlight/part(Assembly)/part_sep。
- 节点图标：command_set_tree_icon {n f} -> tree(icon_file,$n)。

## 5. 消息窗 / 状态 / 偏好

- 构建：make_message_window（guibase.tcl:755）；写入命令 mess <text> <color>? ...（回退 proc mess {text {color black}}，icbqs_server.tcl:16）；红色分级（autohex.tcl:498 的 mess ... red）；启动横幅（whoami/version/copyright，guibase.tcl:828-836）。
- show_logfile 模块（guibase.tcl:568）；状态行 topform_geo/botform_geo。
- 偏好文件（HOME/.icepak_config/.icepak_defaults/.icepak_qnodes）由 configfile 模块读写；启动 uplevel source（autohex.tcl:473-476/527-530）；-use <file> 命令行。
- 字体：default_text_font $normalfont、default_title_font $bigfont；option add *font（guibase.tcl:625-634）；黑白 tk_setPalette white。

## 6. AutoHex 网格参数（params_auto.tcl 全表要点）

- 尺寸：grid_type / grid_usesize_x|y|z|h / grid_size_x|y|z=1 / grid_max_elements=25000000。
- 齿距：grid_gcount_i|j|k=10 / grid_gtype=unif / grid_sep_x|y|z=0.001(m) / grid_gratio(i|j|k){init=0,rat=1,dir=0}。
- Mesher 预设 normal/coarse/null：min_elements_gap 3/2/1、min_elements_block 2/1/1、max_ratio 2/10/10000、conformal_tol 0.01、cyl_shrink_factor 0.99。
- Tetra：n_cells_in_gap 2/1、natural_size_refinement 32/8。HDM：mlm_auto_levels=2、icechip=1、feature_angle=40。Smoother：limit_bad_angle=35、mth_local_sm=Optimize。质量：bad_face_align 0.05 等。pipe：pipe_mesh_params(on=0, ogrid_height=0.5)。
- 各类型侧边名 grid_side_names；网格生成流程 edit_grid_check_meshers -> edit_grid -> mesher/tetra/global/hexa/hdm/iceboard_meshing/smooth/cutter；批量 grid_generate + grid_compute_quality（init:787-789）。

## 7. Batch Queue（batch_queue 命名空间）

- init_queue system（IcBQS/PBS/GridEngine/Ansys，batch_queue.tcl:148）；选项 -servers/-port/-mode/-pfunc/-use_ssl；默认端口 6791（icbqs_server.tcl:92）。
- submit_job：-priority(默认1)/-dispatch/-logfile/-server/-max_time（L194-246）；状态 RUNNING/QUEUED/TERMINATED/FINISHED/FAILURE/UNKNOWN；任务属性 LOGFILE/COMMAND/HOST/MODE/PID/STATUS/PRIORITY/QUEUE/SYSTEM/MAX_TIME/START_TIME/STOP_TIME/MESSAGES（_job_properties_list :889-892）。
- 客户端 rsh 启动远端 icbqs_server_setup.tcl（:193-202）。

## 8. 其它关键开关（init_icepak.tcl）

- 布局：ICEPAK_USE_MENUBAR=1/ICEPAK_ONE_WINDOW=1/tree_on_left=1/tree_has_libraries=1/no_main_window_logo=1/mainwindow_menu_pad=0/allow_multiple_views=1/no_menu_tearoff=1/use_builtin_file_dialogs=1。
- 功能：use_nonconformal_meshing=1/want_local_coord_systems=1/want_icepak_tree_stuff=1/want_cartesian_auto_mesher=1/want_grid_export_tab=1/want_trial_restart_ids=1/object_edit_use_notebook=1/use_indomain_button=1/selectbg_color=#99d9ea/default_side_family=WALL/default_families_from_object_names=0。
- 启动：Welcome（Existing/New/Unpack/Quit）；命令行 tool_options（-batch_solve_id/-batch_report_file/-batch_just_check/-batch_just_report/-uns/-qserve/-regression/-batch_report_xyfile）。
- 后处理对象：post_create objsurface|planecut|isosurface|point；post_plot convergence|variation|3dgraph|history|trials。
- Workbench：IcePakServer::Start port/client IP（icepakwb_server.tcl，tool_setup_app :362-367）；File 菜单差异见 menus_icepak.tcl:170-211。

## 9. 已知的编译模块内内容（不可读，需运行时探针）

- make_main_window 内部控件树（.v 下 widgets）、make_message_window 内部、make_tool_windows 内部。
- AutoHex 对话框六页签控件布局（字段/默认值已由 params_auto.tcl 补全）。
- 队列配置面板（参数语义已由 batch_queue.tcl 补全）。
- 树的具体结点文本（已由 form_set_label_text + 教程图 3-67/3-69 补全）。

> 还原途径：运行时 Tcl 动态读取（本会话未运行 GUI——需在装有该软件的开发机启动后 dump winfo children），或按上述三源交叉实现并截图核对。