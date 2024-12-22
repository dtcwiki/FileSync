import sys
import os
import logging
from PyQt5 import QtWidgets, QtGui, QtCore
from gui.main_window import MainWindow
from config_manager import ConfigManager
from file_monitor import FileMonitor
from sync_manager import SyncManager
import queue

def setup_logging():
    """设置日志记录"""
    os.makedirs('log', exist_ok=True)
    logging.basicConfig(
        filename='log/app.log',
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        encoding='utf-8'
    )

def main():
    """程序入口点"""
    # 设置日志
    setup_logging()
    logging.info("程序启动")

    # 创建应用实例
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')  # 使用Fusion风格使界面更现代

    # 设置应用程序图标和主题
    app.setWindowIcon(QtGui.QIcon('gui/icons/app.svg'))
    
    # 创建配置管理器实例
    config_manager = ConfigManager()
    
    # 创建文件监控器实例
    file_monitor = FileMonitor()
    
    # 创建同步管理器实例
    sync_manager = SyncManager()
    
    # 创建主窗口
    main_window = MainWindow(config_manager, file_monitor, sync_manager)
    main_window.show()
    
    # 启动事件循环
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()