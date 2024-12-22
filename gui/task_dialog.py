import os
from PyQt5 import QtWidgets, QtGui, QtCore
import queue


class TaskDialog(QtWidgets.QDialog):
    """任务配置对话框"""
    
    def __init__(self, parent=None, task=None):
        super().__init__(parent)
        self.task = task
        self.init_ui()
        
        if task:
            self.load_task_data(task)
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("配置同步任务")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # 任务名称
        name_layout = QtWidgets.QHBoxLayout()
        name_label = QtWidgets.QLabel("任务名称:")
        self.name_input = QtWidgets.QLineEdit()
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        # 协议选择
        protocol_layout = QtWidgets.QHBoxLayout()
        protocol_label = QtWidgets.QLabel("同步协议:")
        self.protocol_combo = QtWidgets.QComboBox()
        self.protocol_combo.addItems(["SFTP", "FTP", "WebDAV"])
        self.protocol_combo.currentTextChanged.connect(self.on_protocol_changed)
        protocol_layout.addWidget(protocol_label)
        protocol_layout.addWidget(self.protocol_combo)
        layout.addLayout(protocol_layout)
        
        # 服务器配置组
        server_group = QtWidgets.QGroupBox("服务器配置")
        server_layout = QtWidgets.QGridLayout()
        
        # 主机名
        self.host_label = QtWidgets.QLabel("主机名:")
        self.host_input = QtWidgets.QLineEdit()
        server_layout.addWidget(self.host_label, 0, 0)
        server_layout.addWidget(self.host_input, 0, 1)
        
        # 端口
        self.port_label = QtWidgets.QLabel("端口:")
        self.port_input = QtWidgets.QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(22)  # 默认SFTP端口
        server_layout.addWidget(self.port_label, 0, 2)
        server_layout.addWidget(self.port_input, 0, 3)
        
        # 用户名
        username_label = QtWidgets.QLabel("用户名:")
        self.username_input = QtWidgets.QLineEdit()
        server_layout.addWidget(username_label, 1, 0)
        server_layout.addWidget(self.username_input, 1, 1)
        
        # 认证方式
        self.auth_group = QtWidgets.QGroupBox("认证方式")
        auth_layout = QtWidgets.QVBoxLayout()
        
        # 密码认证
        self.password_radio = QtWidgets.QRadioButton("密码认证")
        self.password_radio.setChecked(True)
        self.password_input = QtWidgets.QLineEdit()
        self.password_input.setEchoMode(QtWidgets.QLineEdit.Password)
        auth_layout.addWidget(self.password_radio)
        auth_layout.addWidget(self.password_input)
        
        # 密钥认证（仅SFTP）
        self.key_auth_radio = QtWidgets.QRadioButton("密钥认证")
        self.key_path_input = QtWidgets.QLineEdit()
        self.key_path_input.setEnabled(False)
        key_browse_button = QtWidgets.QPushButton("浏览...")
        key_browse_button.clicked.connect(self.browse_key_file)
        
        key_layout = QtWidgets.QHBoxLayout()
        key_layout.addWidget(self.key_path_input)
        key_layout.addWidget(key_browse_button)
        
        auth_layout.addWidget(self.key_auth_radio)
        auth_layout.addLayout(key_layout)
        
        # 连接认证方式选择信号
        self.password_radio.toggled.connect(self.on_auth_method_changed)
        self.key_auth_radio.toggled.connect(self.on_auth_method_changed)
        
        self.auth_group.setLayout(auth_layout)
        server_layout.addWidget(self.auth_group, 2, 0, 1, 4)
        
        server_group.setLayout(server_layout)
        layout.addWidget(server_group)
        
        # 目录配置组
        dir_group = QtWidgets.QGroupBox("目录配置")
        dir_layout = QtWidgets.QGridLayout()
        
        # 扫描间隔设置
        interval_label = QtWidgets.QLabel("扫描间隔(秒):")
        self.interval_input = QtWidgets.QSpinBox()
        self.interval_input.setRange(1, 3600)  # 1秒到1小时
        self.interval_input.setValue(5)  # 默认5秒
        dir_layout.addWidget(interval_label, 0, 0)
        dir_layout.addWidget(self.interval_input, 0, 1)
        
        # 本地目录
        local_dir_label = QtWidgets.QLabel("本地目录:")
        self.local_dir_input = QtWidgets.QLineEdit()
        local_dir_browse = QtWidgets.QPushButton("浏览...")
        local_dir_browse.clicked.connect(self.browse_local_dir)
        
        dir_layout.addWidget(local_dir_label, 1, 0)
        dir_layout.addWidget(self.local_dir_input, 1, 1)
        dir_layout.addWidget(local_dir_browse, 1, 2)
        
        # 远程目录
        remote_dir_label = QtWidgets.QLabel("远程目录:")
        self.remote_dir_input = QtWidgets.QLineEdit()
        
        dir_layout.addWidget(remote_dir_label, 2, 0)
        dir_layout.addWidget(self.remote_dir_input, 2, 1, 1, 2)
        
        dir_group.setLayout(dir_layout)
        layout.addWidget(dir_group)
        
        # 按钮
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)
        # 设置按钮文本
        button_box.button(QtWidgets.QDialogButtonBox.Ok).setText("确定")
        button_box.button(QtWidgets.QDialogButtonBox.Cancel).setText("取消")
        layout.addWidget(button_box)
        
        # 设置样式
        self.setStyleSheet("""
            QDialog {
                background-color: #f0f0f0;
                font-family: 'Microsoft YaHei';
            }
            QGroupBox {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 4px;
                margin-top: 1ex;
                padding: 10px;
                font-family: 'Microsoft YaHei';
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
                font-family: 'Microsoft YaHei';
            }
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-family: 'Microsoft YaHei';
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
            QLineEdit, QSpinBox, QComboBox {
                padding: 5px;
                border: 1px solid #ddd;
                border-radius: 3px;
                font-family: 'Microsoft YaHei';
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border-color: #007bff;
            }
            QLabel {
                font-family: 'Microsoft YaHei';
            }
            QRadioButton {
                font-family: 'Microsoft YaHei';
            }
        """)
    
    def on_protocol_changed(self, protocol: str):
        """处理协议变更"""
        # 更新端口显示和默认值
        if protocol == "SFTP":
            self.port_input.setValue(22)
            self.key_auth_radio.setEnabled(True)
            self.port_label.setVisible(True)
            self.port_input.setVisible(True)
            self.host_label.setText("主机名:")
        elif protocol == "FTP":
            self.port_input.setValue(21)
            self.key_auth_radio.setEnabled(False)
            self.password_radio.setChecked(True)
            self.port_label.setVisible(True)
            self.port_input.setVisible(True)
            self.host_label.setText("主机名:")
        else:  # WebDAV
            self.port_input.setVisible(False)
            self.port_label.setVisible(False)
            self.key_auth_radio.setEnabled(False)
            self.password_radio.setChecked(True)
            self.host_label.setText("主机名: (例如: https://example.com/webdav)")
    
    def on_auth_method_changed(self):
        """处理认证方式变更"""
        is_password_auth = self.password_radio.isChecked()
        self.password_input.setEnabled(is_password_auth)
        self.key_path_input.setEnabled(not is_password_auth)
    
    def browse_key_file(self):
        """浏览选择密钥文件"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "选择密钥文件",
            os.path.expanduser("~/.ssh"),
            "All Files (*.*)"
        )
        if file_path:
            self.key_path_input.setText(file_path)
    
    def browse_local_dir(self):
        """浏览选择本地目录"""
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "选择本地目录",
            os.path.expanduser("~")
        )
        if dir_path:
            self.local_dir_input.setText(dir_path)
    
    def validate_and_accept(self):
        """验证输入并接受对话框"""
        # 验证必填字段
        if not self.name_input.text():
            self.show_error("请输入任务名称")
            return
        
        # 验证主机名
        host = self.host_input.text()
        if not host:
            self.show_error("请输入主机名")
            return
        
        # 对WebDAV进行特殊验证
        if self.protocol_combo.currentText() == "WebDAV":
            if not (host.startswith('http://') or host.startswith('https://')):
                self.show_error("WebDAV主机名必须以http://或https://开头")
                return
        
        if not self.username_input.text():
            self.show_error("请输入用户名")
            return
        
        if self.password_radio.isChecked() and not self.password_input.text():
            self.show_error("请输入密码")
            return
        
        if self.key_auth_radio.isChecked() and not self.key_path_input.text():
            self.show_error("请选择密钥文件")
            return
        
        if not self.local_dir_input.text():
            self.show_error("请选择本地目录")
            return
        
        if not self.remote_dir_input.text():
            self.show_error("请输入远程目录")
            return
        
        self.accept()
    
    def show_error(self, message: str):
        """显示错误消息"""
        QtWidgets.QMessageBox.critical(self, "错误", message)
    
    def get_task_data(self) -> dict:
        """获取任务配置数据"""
        task_data = {
            'name': self.name_input.text(),
            'protocol': self.protocol_combo.currentText(),
            'host': self.host_input.text(),
            'port': self.port_input.value(),
            'username': self.username_input.text(),
            'local_dir': self.local_dir_input.text(),
            'remote_dir': self.remote_dir_input.text(),
            'use_key_auth': self.key_auth_radio.isChecked(),
            'scan_interval': self.interval_input.value()
        }
        
        if self.password_radio.isChecked():
            task_data['password'] = self.password_input.text()
        else:
            task_data['key_path'] = self.key_path_input.text()
        
        return task_data
    
    def load_task_data(self, task: dict):
        """加载任务配置数据"""
        self.name_input.setText(task['name'])
        self.protocol_combo.setCurrentText(task['protocol'])
        self.host_input.setText(task['host'])
        self.port_input.setValue(task['port'])
        self.username_input.setText(task['username'])
        self.local_dir_input.setText(task['local_dir'])
        self.remote_dir_input.setText(task['remote_dir'])
        self.interval_input.setValue(task.get('scan_interval', 5))
        
        if task.get('use_key_auth', False):
            self.key_auth_radio.setChecked(True)
            self.key_path_input.setText(task.get('key_path', ''))
        else:
            self.password_radio.setChecked(True)
            self.password_input.setText(task.get('password', ''))
