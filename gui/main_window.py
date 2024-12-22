import os
import uuid
import time
import json
import logging
from PyQt5 import QtWidgets, QtGui, QtCore
from .task_dialog import TaskDialog
from typing import Dict, Set
import queue
class MainWindow(QtWidgets.QMainWindow):
    """主窗口类"""
    
    def __init__(self, config_manager, file_monitor, sync_manager):
        super().__init__()
        self.config_manager = config_manager
        self.file_monitor = file_monitor
        self.sync_manager = sync_manager
        self.active_tasks: Dict[str, dict] = {}
        self.task_timers: Dict[str, QtCore.QTimer] = {}
        
        # 创建系统托盘
        self.tray_icon = None
        
        # 创建系统托盘
        self.tray_icon = None
        self.init_tray()
        
        self.init_ui()
        self.load_tasks()
        
        self.setWindowTitle("文件同步工具")
        
        icon_path = os.path.join(os.path.dirname(__file__), 'icons', 'app.ico')
        self.setWindowIcon(QtGui.QIcon(icon_path))
    
    def init_tray(self):
        """初始化系统托盘"""
        # 创建托盘图标菜单
        self.tray_menu = QtWidgets.QMenu()
        show_action = self.tray_menu.addAction("显示主窗口")
        show_action.triggered.connect(self.show)
        quit_action = self.tray_menu.addAction("退出程序")
        quit_action.triggered.connect(self.quit_app)
        
        # 创建托盘图标
        tray_icon_path = os.path.join(os.path.dirname(__file__), 'icons', 'app.ico')
        self.tray_icon = QtWidgets.QSystemTrayIcon(self)
        self.tray_icon.setIcon(QtGui.QIcon(tray_icon_path))
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()
        
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("文件同步工具")
        self.setGeometry(100, 100, 1000, 600)  # 增加窗口宽度
        
        # 设置应用字体
        app = QtWidgets.QApplication.instance()
        app.setFont(QtGui.QFont("Microsoft YaHei", 9))
        
        # 创建中央部件
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        layout = QtWidgets.QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)  # 增加边距
        
        # 创建任务列表
        self.task_list = QtWidgets.QTableWidget()
        self.task_list.setColumnCount(6)
        self.task_list.setHorizontalHeaderLabels([
            "任务名称", "协议", "本地目录", "远程目录", "状态", "操作"
        ])
        
        # 设置表格样式
        self.task_list.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)  # 任务名称
        self.task_list.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)  # 协议
        self.task_list.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)  # 本地目录
        self.task_list.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)  # 远程目录
        self.task_list.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)  # 状态
        self.task_list.horizontalHeader().setSectionResizeMode(5, QtWidgets.QHeaderView.Fixed)  # 操作
        self.task_list.setColumnWidth(5, 140)  # 调整操作列宽度
        
        # 设置行高和其他样式
        self.task_list.verticalHeader().setDefaultSectionSize(80)  # 增加行高
        self.task_list.verticalHeader().hide()  # 隐藏垂直表头
        self.task_list.verticalHeader().setStyleSheet("""
            QHeaderView::section {
                background-color: white;
                padding: 4px;
                border: none;
                border-right: 1px solid #eee;
            }
        """)
        self.task_list.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QTableWidget::item {
                padding: 12px;
                border-bottom: 1px solid #eee;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 12px;
                border: none;
                border-bottom: 1px solid #ddd;
                font-weight: bold;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
            }
            QScrollBar:vertical {
                border: 1px solid #E0E0E0;
                background: white;
                width: 16px;
                margin: 16px 0 16px 0;
            }
            QScrollBar::handle:vertical {
                background: #BDBDBD;
                min-height: 20px;
                border: 1px solid #E0E0E0;
            }
            QScrollBar::add-line:vertical {
                border: 1px solid #E0E0E0;
                background: #F5F5F5;
                height: 16px;
                subcontrol-position: bottom;
                subcontrol-origin: margin;
            }
            QScrollBar::sub-line:vertical {
                border: 1px solid #E0E0E0;
                background: #F5F5F5;
                height: 16px;
                subcontrol-position: top;
                subcontrol-origin: margin;
            }
            QScrollBar::up-arrow:vertical {
                width: 8px;
                height: 8px;
                border: 1px solid #BDBDBD;
                background: #BDBDBD;
                image: url(data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='8' viewBox='0 0 8 8'%3E%3Cpath fill='white' d='M4 0l4 4h-8z'/%3E%3C/svg%3E);
            }
            QScrollBar::down-arrow:vertical {
                width: 8px;
                height: 8px;
                border: 1px solid #BDBDBD;
                background: #BDBDBD;
                image: url(data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='8' viewBox='0 0 8 8'%3E%3Cpath fill='white' d='M0 0h8l-4 4z'/%3E%3C/svg%3E);
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: #F5F5F5;
            }
            QScrollBar:horizontal {
                border: 1px solid #E0E0E0;
                background: white;
                height: 16px;
                margin: 0 16px 0 16px;
            }
            QScrollBar::handle:horizontal {
                background: #BDBDBD;
                min-width: 20px;
                border: 1px solid #E0E0E0;
            }
            QScrollBar::add-line:horizontal {
                border: 1px solid #E0E0E0;
                background: #F5F5F5;
                width: 16px;
                subcontrol-position: right;
                subcontrol-origin: margin;
            }
            QScrollBar::sub-line:horizontal {
                border: 1px solid #E0E0E0;
                background: #F5F5F5;
                width: 16px;
                subcontrol-position: left;
                subcontrol-origin: margin;
            }
            QScrollBar::left-arrow:horizontal {
                width: 8px;
                height: 8px;
                border: 1px solid #BDBDBD;
                background: #BDBDBD;
                image: url(data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='8' viewBox='0 0 8 8'%3E%3Cpath fill='white' d='M4 0l4 8h-8z' transform='rotate(-90 4 4)'/%3E%3C/svg%3E);
            }
            QScrollBar::right-arrow:horizontal {
                width: 8px;
                height: 8px;
                border: 1px solid #BDBDBD;
                background: #BDBDBD;
                image: url(data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='8' viewBox='0 0 8 8'%3E%3Cpath fill='white' d='M0 0h8l-4 4z' transform='rotate(90 4 4)'/%3E%3C/svg%3E);
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: #F5F5F5;
            }
        """)
        
        # 启用滚动条
        self.task_list.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.task_list.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        
        # 允许自动换行显示
        self.task_list.setWordWrap(True)
        self.task_list.verticalHeader().setDefaultAlignment(QtCore.Qt.AlignTop)
        layout.addWidget(self.task_list)
        
        # 创建底部按钮布局
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)  # 增加上边距
        
        # 添加新任务按钮
        add_button = QtWidgets.QPushButton("添加任务")
        add_button.setMinimumWidth(120)  # 设置最小宽度
        add_button.setMinimumHeight(36)  # 设置最小高度
        add_button.clicked.connect(self.show_add_task_dialog)
        button_layout.addWidget(add_button)
        button_layout.addStretch()  # 添加弹性空间
        
        # 添加底部布局
        layout.addLayout(button_layout)
        
        # 设置窗口样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QPushButton {
                background-color: #1976d2;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
            QPushButton:pressed {
                background-color: #0d47a1;
            }
        """)
    
    def _add_task_to_table(self, row: int, task: dict):
        """将任务添加到表格中"""
        # 设置任务信息
        self.task_list.setItem(row, 0, QtWidgets.QTableWidgetItem(task['name']))
        self.task_list.setItem(row, 1, QtWidgets.QTableWidgetItem(task['protocol']))
        self.task_list.setItem(row, 2, QtWidgets.QTableWidgetItem(task['local_dir']))
        self.task_list.setItem(row, 3, QtWidgets.QTableWidgetItem(task['remote_dir']))
        
        # 设置状态
        status = "未运行"
        if task['id'] in self.active_tasks:
            status = "运行中"
        status_item = QtWidgets.QTableWidgetItem(status)
        status_item.setTextAlignment(QtCore.Qt.AlignCenter)
        self.task_list.setItem(row, 4, status_item)
        
        # 创建操作按钮容器
        button_widget = QtWidgets.QWidget()
        button_layout = QtWidgets.QHBoxLayout(button_widget)
        button_layout.setSpacing(8)  # 调整按钮间距
        button_layout.setContentsMargins(4, 4, 4, 4)  # 调整边距
        button_layout.setAlignment(QtCore.Qt.AlignCenter)  # 居中对齐
        
        # 开始/停止按钮
        toggle_button = QtWidgets.QPushButton()
        # 设置图标颜色为白色
        icon = QtGui.QIcon('gui/icons/stop.svg' if status == "运行中" else 'gui/icons/start.svg')
        pixmap = icon.pixmap(20, 20)
        painter = QtGui.QPainter(pixmap)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QtGui.QColor('white'))
        painter.end()
        toggle_button.setIcon(QtGui.QIcon(pixmap))
        toggle_button.setIconSize(QtCore.QSize(20, 20))
        toggle_button.setToolTip("停止" if status == "运行中" else "启动")
        toggle_button.setFixedSize(32, 32)
        toggle_button.setStyleSheet("""
            QPushButton {
                background-color: #2196f3;
                border-radius: 16px;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #1976d2;
            }
        """)
        toggle_button.clicked.connect(lambda: self.toggle_task(task))
        button_layout.addWidget(toggle_button)
        
        # 编辑按钮
        edit_button = QtWidgets.QPushButton()
        # 设置编辑图标颜色为白色
        icon = QtGui.QIcon('gui/icons/edit.svg')
        pixmap = icon.pixmap(20, 20)
        painter = QtGui.QPainter(pixmap)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QtGui.QColor('white'))
        painter.end()
        edit_button.setIcon(QtGui.QIcon(pixmap))
        edit_button.setIconSize(QtCore.QSize(20, 20))
        edit_button.setToolTip("编辑")
        edit_button.setFixedSize(32, 32)
        edit_button.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                border-radius: 16px;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #388e3c;
            }
        """)
        edit_button.clicked.connect(lambda: self.edit_task(task))
        button_layout.addWidget(edit_button)
        
        # 删除按钮
        delete_button = QtWidgets.QPushButton()
        # 设置删除图标颜色为白色
        icon = QtGui.QIcon('gui/icons/delete.svg')
        pixmap = icon.pixmap(20, 20)
        painter = QtGui.QPainter(pixmap)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QtGui.QColor('white'))
        painter.end()
        delete_button.setIcon(QtGui.QIcon(pixmap))
        delete_button.setIconSize(QtCore.QSize(20, 20))
        delete_button.setToolTip("删除")
        delete_button.setFixedSize(32, 32)
        delete_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                border-radius: 16px;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        delete_button.clicked.connect(lambda: self.delete_task(task))
        button_layout.addWidget(delete_button)
        
        self.task_list.setCellWidget(row, 5, button_widget)
    
    def load_tasks(self):
        """从配置加载任务并自动启动"""
        tasks = self.config_manager.get_sync_tasks()
        self.task_list.setRowCount(len(tasks))
        
        # 先加载所有任务
        for i, task in enumerate(tasks):
            self._add_task_to_table(i, task)
            
        # 自动启动所有任务
        for task in tasks:
            self.start_task(task, show_message=False)
            
        # 刷新表格显示
        self.task_list.setRowCount(0)
        self.task_list.setRowCount(len(tasks))
        for i, task in enumerate(tasks):
            self._add_task_to_table(i, task)
    
    def show_add_task_dialog(self):
        """显示添加任务对话框"""
        dialog = TaskDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            task = dialog.get_task_data()
            task['id'] = str(uuid.uuid4())
            
            if self.config_manager.add_sync_task(task):
                row = self.task_list.rowCount()
                self.task_list.insertRow(row)
                self._add_task_to_table(row, task)
    
    def edit_task(self, task: dict):
        """编辑任务"""
        dialog = TaskDialog(self, task)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            updated_task = dialog.get_task_data()
            updated_task['id'] = task['id']
            
            if self.config_manager.update_sync_task(task['id'], updated_task):
                self.load_tasks()  # 重新加载任务列表
    
    def delete_task(self, task: dict):
        """删除任务"""
        reply = QtWidgets.QMessageBox.question(
            self,
            '确认删除',
            f'确定要删除任务 "{task["name"]}" 吗？',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            # 如果任务正在运行，先停止它
            if task['id'] in self.active_tasks:
                self.stop_task(task)
            
            if self.config_manager.remove_sync_task(task['id']):
                self.load_tasks()  # 重新加载任务列表
    
    def _refresh_task_status(self, task: dict):
        """刷新指定任务的状态显示"""
        # 查找任务所在行
        for row in range(self.task_list.rowCount()):
            if self.task_list.item(row, 0).text() == task['name']:
                # 更新状态文本
                status = "运行中" if task['id'] in self.active_tasks else "未运行"
                status_item = QtWidgets.QTableWidgetItem(status)
                status_item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.task_list.setItem(row, 4, status_item)
                
                # 更新按钮状态
                button_widget = self.task_list.cellWidget(row, 5)
                if button_widget:
                    toggle_button = button_widget.layout().itemAt(0).widget()
                    # 更新图标
                    icon = QtGui.QIcon('gui/icons/stop.svg' if status == "运行中" else 'gui/icons/start.svg')
                    pixmap = icon.pixmap(20, 20)
                    painter = QtGui.QPainter(pixmap)
                    painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
                    painter.fillRect(pixmap.rect(), QtGui.QColor('white'))
                    painter.end()
                    toggle_button.setIcon(QtGui.QIcon(pixmap))
                    toggle_button.setToolTip("停止" if status == "运行中" else "启动")
                break
    
    def toggle_task(self, task: dict):
        """切换任务状态"""
        if task['id'] in self.active_tasks:
            if self.stop_task(task):
                self._refresh_task_status(task)
        else:
            if self.start_task(task):
                self._refresh_task_status(task)
    
    def start_task(self, task: dict, show_message: bool = True) -> bool:
        """启动同步任务"""
        try:
            # 如果任务已经在运行，直接返回成功
            if task['id'] in self.active_tasks:
                return True
                
            # 创建连接
            if not self.sync_manager.create_connection(task['id'], task):
                raise Exception("无法创建连接")
            
            # 设置回调函数
            def sync_callback(directory: str, added: set, modified: set, deleted: set):
                try:
                    # 处理新增和修改的文件
                    for local_path in added | modified:
                        # 计算相对路径并规范化远程路径
                        relative_path = os.path.relpath(local_path, directory)
                        remote_path = os.path.normpath(os.path.join(task['remote_dir'], relative_path))
                        # 转换为Unix风格路径
                        remote_path = remote_path.replace('\\', '/')
                        # 确保路径以/开头
                        if not remote_path.startswith('/'):
                            remote_path = '/' + remote_path
                        
                        # 同步文件并验证
                        success = self.sync_manager.sync_file(task['id'], local_path, remote_path, 'upload')
                        if success:
                            # 验证远程文件
                            if self.sync_manager.verify_remote_file(task['id'], local_path, remote_path):
                                logging.info(f"同步文件成功并验证: {local_path} -> {remote_path}")
                            else:
                                logging.error(f"文件同步验证失败: {local_path} -> {remote_path}")
                                success = False
                        else:
                            logging.error(f"同步文件失败: {local_path} -> {remote_path}")
                    
                    # 处理删除的文件
                    for local_path in deleted:
                        relative_path = os.path.relpath(local_path, directory)
                        remote_path = os.path.normpath(os.path.join(task['remote_dir'], relative_path))
                        remote_path = remote_path.replace('\\', '/')
                        if not remote_path.startswith('/'):
                            remote_path = '/' + remote_path
                        success = self.sync_manager.sync_file(task['id'], '', remote_path, 'delete')
                        if success:
                            logging.info(f"删除远程文件成功: {remote_path}")
                        else:
                            logging.error(f"删除远程文件失败: {remote_path}")
                except Exception as e:
                    logging.error(f"同步回调执行失败: {str(e)}")
            
            # 开始监控，使用配置的扫描间隔
            if self.file_monitor.start_monitoring(task['local_dir'], task['remote_dir'], task.get('scan_interval', 5)):
                self.active_tasks[task['id']] = task
                # 移除启动提示弹窗
                logging.info(f"任务 \"{task['name']}\" 已启动")
                
                # 启动定时器检查日志队列
                timer = QtCore.QTimer(self)
                timer.timeout.connect(lambda: self._check_task_logs(task))
                timer.start(1000)  # 每秒检查一次
                self.task_timers[task['id']] = timer
                
                return True
            else:
                raise Exception("无法启动文件监控")
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"启动任务失败: {str(e)}"
            )
            # 清理连接
            self.sync_manager.close_connection(task['id'])
            return False
    
    def _check_task_logs(self, task: dict):
        """检查任务的日志队列"""
        try:
            log_queue = self.file_monitor.log_queues.get(task['local_dir'])
            if log_queue:
                try:
                    while True:
                        try:
                            message = log_queue.get_nowait()
                            if message == "SYNC_REQUIRED":
                                # 处理同步请求
                                self._sync_task_changes(task)
                            else:
                                self._handle_file_changes_from_log(task, message)
                        except queue.Empty:
                            break
                except Exception as e:
                    logging.error(f"处理日志消息失败: {str(e)}")
        except Exception as e:
            logging.error(f"检查任务日志失败: {str(e)}")
            
    def _sync_task_changes(self, task: dict):
        """同步任务的文件变化"""
        try:
            # 获取哈希值文件
            current_file, _ = self.file_monitor._get_hash_files(task['local_dir'], task['remote_dir'])
            
            # 加载当前哈希值
            with open(current_file, 'r', encoding='utf-8') as f:
                current_hashes = json.load(f)
                
            # 同步所有文件
            for local_path, _ in current_hashes.items():
                # 计算相对路径并规范化远程路径
                relative_path = os.path.relpath(local_path, task['local_dir'])
                remote_path = os.path.normpath(os.path.join(task['remote_dir'], relative_path))
                remote_path = remote_path.replace('\\', '/')
                if not remote_path.startswith('/'):
                    remote_path = '/' + remote_path
                    
                # 同步文件并验证
                success = self.sync_manager.sync_file(task['id'], local_path, remote_path, 'upload')
                if success:
                    if self.sync_manager.verify_remote_file(task['id'], local_path, remote_path):
                        logging.info(f"同步文件成功并验证: {local_path} -> {remote_path}")
                    else:
                        logging.error(f"文件同步验证失败: {local_path} -> {remote_path}")
                else:
                    logging.error(f"同步文件失败: {local_path} -> {remote_path}")
                    
        except Exception as e:
            logging.error(f"同步任务变化失败: {str(e)}")
    
    def _handle_file_changes_from_log(self, task: dict, message: str):
        """从日志消息中解析并处理文件变化"""
        try:
            if "检测到文件变化" in message:
                # 解析JSON格式的变化信息
                start = message.find("{")
                end = message.rfind("}")
                if start != -1 and end != -1:
                    changes_json = message[start:end+1]
                    changes = json.loads(changes_json)
                    
                    # 处理文件变化
                    self._handle_file_changes(task, 
                        set(changes.get("added", [])),
                        set(changes.get("modified", [])),
                        set(changes.get("deleted", [])))
            else:
                # 记录其他类型的���志消息
                logging.info(message)
        except json.JSONDecodeError as e:
            logging.error(f"解析日志消息失败: {str(e)}")
        except Exception as e:
            logging.error(f"处理文件变化日志失败: {str(e)}")
    
    def _handle_file_changes(self, task: dict, added: Set[str], modified: Set[str], deleted: Set[str]):
        """处理文件变化"""
        try:
            # 处理新增和修改的文件
            for local_path in added | modified:
                # 计算相对路径并规范化远程路径
                relative_path = os.path.relpath(local_path, task['local_dir'])
                remote_path = os.path.normpath(os.path.join(task['remote_dir'], relative_path))
                # 转换为Unix风格路径
                remote_path = remote_path.replace('\\', '/')
                # 确保路径以/开头
                if not remote_path.startswith('/'):
                    remote_path = '/' + remote_path
                
                # 同步文件并验证
                success = self.sync_manager.sync_file(task['id'], local_path, remote_path, 'upload')
                if success:
                    # 验证远程文件
                    if self.sync_manager.verify_remote_file(task['id'], local_path, remote_path):
                        logging.info(f"同步文件成功并验证: {local_path} -> {remote_path}")
                    else:
                        logging.error(f"文件同步验证失败: {local_path} -> {remote_path}")
                else:
                    logging.error(f"同步文件失败: {local_path} -> {remote_path}")
            
            # 处理删除的文件
            for local_path in deleted:
                relative_path = os.path.relpath(local_path, task['local_dir'])
                remote_path = os.path.normpath(os.path.join(task['remote_dir'], relative_path))
                remote_path = remote_path.replace('\\', '/')
                if not remote_path.startswith('/'):
                    remote_path = '/' + remote_path
                success = self.sync_manager.sync_file(task['id'], '', remote_path, 'delete')
                if success:
                    logging.info(f"删除远程文件成功: {remote_path}")
                else:
                    logging.error(f"删除远程文件失败: {remote_path}")
                    
        except Exception as e:
            logging.error(f"处理文件变化失败: {str(e)}")
    
    def stop_task(self, task: dict) -> bool:
        """停止同步任务"""
        try:
            # 如果任务不在运行，直接返回成功
            if task['id'] not in self.active_tasks:
                return True
                
            # 停止文件监控
            self.file_monitor.stop_monitoring(task['local_dir'])
            
            # 等待进程完全停止
            time.sleep(1)
            
            # 关闭连接
            self.sync_manager.close_connection(task['id'])
            
            # 停止并清理定时器
            if task['id'] in self.task_timers:
                self.task_timers[task['id']].stop()
                self.task_timers[task['id']].deleteLater()
                del self.task_timers[task['id']]
            
            # 从活动任务中移除
            del self.active_tasks[task['id']]
            
            logging.info(f"任务 \"{task['name']}\" 已停止")
            return True
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "错误",
                f"停止任务失败: {str(e)}"
            )
            return False
    
    def tray_icon_activated(self, reason):
        """处理托盘图标点击事件"""
        if reason == QtWidgets.QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.activateWindow()
    
    def quit_app(self):
        """完全退出应用程序"""
        # 停止所有任务并等待它们完全停止
        for task in list(self.active_tasks.values()):
            self.stop_task(task)
            time.sleep(1)  # 确保每个任务都有足够时间完全停止
        
        # 清理所有定时器
        for timer in self.task_timers.values():
            timer.stop()
            timer.deleteLater()
        self.task_timers.clear()
        
        # 退出应用
        QtWidgets.QApplication.quit()
    
    def closeEvent(self, event: QtGui.QCloseEvent):
        """窗口关闭事件"""
        # 最小化到托盘
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "文件同步工具",
            "程序已最小化到系统托盘，同步任务继续运行",
            QtWidgets.QSystemTrayIcon.Information,
            2000
        )
