import json
import os
import logging
from typing import Dict, List, Optional
import queue


class ConfigManager:
    """配置管理器类，负责处理程序的所有配置相关操作"""
    
    def __init__(self):
        self.config_file = 'config.json'
        self.current_config = self._load_config()
        
    def _load_config(self) -> dict:
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {
                'sync_tasks': [],
                'last_used_protocol': 'SFTP',
                'default_port': {
                    'SFTP': 22,
                    'FTP': 21,
                    'WebDAV': 80
                }
            }
        except Exception as e:
            logging.error(f"加载配置文件失败: {str(e)}")
            return self._get_default_config()
    
    def _get_default_config(self) -> dict:
        """获取默认配置"""
        return {
            'sync_tasks': [],
            'last_used_protocol': 'SFTP',
            'default_port': {
                'SFTP': 22,
                'FTP': 21,
                'WebDAV': 80
            }
        }
    
    def save_config(self) -> bool:
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logging.error(f"保存配置文件失败: {str(e)}")
            return False
    
    def add_sync_task(self, task: dict) -> bool:
        """添加新的同步任务"""
        try:
            self.current_config['sync_tasks'].append(task)
            return self.save_config()
        except Exception as e:
            logging.error(f"添加同步任务失败: {str(e)}")
            return False
    
    def remove_sync_task(self, task_id: str) -> bool:
        """删除同步任务"""
        try:
            self.current_config['sync_tasks'] = [
                task for task in self.current_config['sync_tasks']
                if task['id'] != task_id
            ]
            return self.save_config()
        except Exception as e:
            logging.error(f"删除同步任务失败: {str(e)}")
            return False
    
    def update_sync_task(self, task_id: str, updated_task: dict) -> bool:
        """更新同步任务"""
        try:
            for i, task in enumerate(self.current_config['sync_tasks']):
                if task['id'] == task_id:
                    self.current_config['sync_tasks'][i] = updated_task
                    return self.save_config()
            return False
        except Exception as e:
            logging.error(f"更新同步任务失败: {str(e)}")
            return False
    
    def get_sync_tasks(self) -> List[dict]:
        """获取所有同步任务"""
        return self.current_config.get('sync_tasks', [])
    
    def get_task_by_id(self, task_id: str) -> Optional[dict]:
        """通过ID获取特定同步任务"""
        for task in self.current_config.get('sync_tasks', []):
            if task['id'] == task_id:
                return task
        return None
    
    def get_default_port(self, protocol: str) -> int:
        """获取指定协议的默认端口"""
        return self.current_config['default_port'].get(protocol, 0)
    
    def set_last_used_protocol(self, protocol: str):
        """设置最后使用的协议"""
        self.current_config['last_used_protocol'] = protocol
        self.save_config()
    
    def get_last_used_protocol(self) -> str:
        """获取最后使用的协议"""
        return self.current_config.get('last_used_protocol', 'SFTP')

    def get_monitored_directories(self) -> Dict[str, str]:
        """获取所有需要监控的目录"""
        tasks = self.get_sync_tasks()
        directories = {}
        for task in tasks:
            directories[task['local_dir']] = task['remote_dir']
        return directories
