import PyInstaller.__main__
import os

# 获取当前脚本所在目录
script_dir = os.path.dirname(os.path.abspath(__file__))

# 设置要打包的主程序入口文件
entry_file = os.path.join(script_dir, 'main.py')

# 设置打包选项
options = [
    entry_file,
    '--name=FileSync',  # 可执行文件名
    '--icon=gui/icons/app.ico',  # 可执行文件图标
    '--add-data=gui/icons:gui/icons',  # 打包图标文件夹
    '--hidden-import=pkg_resources.py2_warn',  # 隐藏的导入模块
    '--hidden-import=PyQt5.QtWidgets',  # 确保引入 QtWidgets 模块
    '--noconsole',  # 不显示控制台窗口
    '--onefile'  # 打包成单个可执行文件
]

# 开始打包
PyInstaller.__main__.run(options) 