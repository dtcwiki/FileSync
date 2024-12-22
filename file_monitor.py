import os
import sys
import json
import hashlib
import logging
import time
import queue
from typing import Dict, Set, Tuple
from multiprocessing import Process, Event, Queue, freeze_support

class FileMonitor:
    """文件监控类，负责监控文件夹变化并计算文件哈希值"""
    
    def __init__(self):
        self.monitor_processes: Dict[str, Process] = {}
        self.stop_events: Dict[str, Event] = {}
        self.log_queues: Dict[str, Queue] = {}
        
    def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件的SHA256哈希值"""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            return ""

    def _scan_directory(self, directory: str) -> Dict[str, str]:
        """扫描目录并计算所有文件的哈希值"""
        file_hashes = {}
        try:
            for root, _, files in os.walk(directory):
                for file in files:
                    file_path = os.path.abspath(os.path.join(root, file))
                    file_hash = self._calculate_file_hash(file_path)
                    if file_hash:
                        file_hashes[file_path] = file_hash
        except Exception:
            pass
        return file_hashes

    def _save_hashes(self, hashes: Dict[str, str], file_path: str):
        """保存哈希值到JSON文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(hashes, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    def _load_hashes(self, file_path: str) -> Dict[str, str]:
        """从JSON文件加载哈希值"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _detect_changes(self, current_hashes: Dict[str, str], 
                       previous_hashes: Dict[str, str]) -> Tuple[Set[str], Set[str], Set[str]]:
        """检测文件变化，返回新增、修改和删除的文件集合"""
        current_files = set(current_hashes.keys())
        previous_files = set(previous_hashes.keys())
        
        # 使用绝对路径进行比较
        added_files = current_files - previous_files
        deleted_files = previous_files - current_files
        
        # 检测修改的文件
        modified_files = set()
        for file in current_files & previous_files:
            try:
                if current_hashes[file] != previous_hashes[file]:
                    # 确保文件仍然存在且可访问
                    if os.path.exists(file) and os.access(file, os.R_OK):
                        modified_files.add(file)
            except Exception:
                continue
        
        return added_files, modified_files, deleted_files

    def _get_hash_files(self, directory: str, remote_dir: str) -> Tuple[str, str]:
        """获取指定目录的哈希值文件路径"""
        # 结合本地和远程路径生成唯一标识
        path_hash = hashlib.md5(f"{directory}:{remote_dir}".encode()).hexdigest()
        current_file = f'current_hashes_{path_hash}.json'
        previous_file = f'previous_hashes_{path_hash}.json'
        return current_file, previous_file

    @staticmethod
    def _monitor_process(directory: str, remote_dir: str, stop_event: Event, log_queue: Queue, interval: int = 5):
        """监控进程的主函数"""
        try:
            # 设置进程级日志处理
            logging.basicConfig(level=logging.INFO)
            logging.info(f"开始监控目录: {directory}")
            log_queue.put_nowait(f"开始监控目录: {directory}")
            
            # 创建监控器实例
            monitor = FileMonitor()
            
            # 获取该目录专用的哈希值文件
            current_file, previous_file = monitor._get_hash_files(directory, remote_dir)
            
            # 初始化哈希值文件
            initial_hashes = monitor._scan_directory(directory)
            monitor._save_hashes(initial_hashes, current_file)
            monitor._save_hashes(initial_hashes, previous_file)
            
            while not stop_event.is_set():
                try:
                    # 扫描当前状态
                    current_hashes = monitor._scan_directory(directory)
                    
                    # 加载上次的哈希值
                    previous_hashes = monitor._load_hashes(previous_file)
                    
                    # 检测变化
                    added, modified, deleted = monitor._detect_changes(current_hashes, previous_hashes)
                    
                    # 如果有变化，立即触发同步
                    if added or modified or deleted:
                        changes_info = {
                            "added": list(added),
                            "modified": list(modified),
                            "deleted": list(deleted)
                        }
                        log_queue.put_nowait(f"检测到文件变化: {json.dumps(changes_info)}")
                        
                        # 立即更新哈希值文件并触发同步
                        monitor._save_hashes(current_hashes, current_file)
                        log_queue.put_nowait("SYNC_REQUIRED")  # 发送同步请求
                        
                        # 等待短暂时间后更新previous_file
                        time.sleep(0.5)
                        monitor._save_hashes(current_hashes, previous_file)
                    
                    # 等待下一次扫描
                    time.sleep(interval)
                    
                except Exception as e:
                    logging.error(f"监控目录时发生错误: {str(e)}")
                    log_queue.put_nowait(f"监控目录时发生错误: {str(e)}")
                    stop_event.wait(interval)
                    
        except Exception as e:
            logging.error(f"监控进程发生错误: {str(e)}")
            log_queue.put_nowait(f"监控进程发生错误: {str(e)}")
        finally:
            logging.info(f"停止监控目录: {directory}")
            log_queue.put_nowait(f"停止监控目录: {directory}")

    def start_monitoring(self, directory: str, remote_dir: str, interval: int = 5):
        """开始监控指定目录"""
        if directory in self.monitor_processes:
            if self.monitor_processes[directory].is_alive():
                logging.warning(f"目录 {directory} 已在监控中")
                return False
            else:
                # 如果进程已经结束，清理旧资源
                self.stop_monitoring(directory)
        
        try:
            # 创建新的事件和队列
            stop_event = Event()
            log_queue = Queue()
            
            # 创建并启动进程
            process = Process(
                target=self._monitor_process,
                args=(directory, remote_dir, stop_event, log_queue, interval),
                daemon=True,
                name=f"Monitor-{directory}"
            )
            
            # 保存资源引用
            self.monitor_processes[directory] = process
            self.stop_events[directory] = stop_event
            self.log_queues[directory] = log_queue
            
            # 启动进程
            process.start()
            
            # 等待进程完全启动
            time.sleep(0.5)
            
            if process.is_alive():
                logging.info(f"成功启动监控目录: {directory}")
                return True
            else:
                logging.error("进程启动失败")
                self.stop_monitoring(directory)
                return False
            
        except Exception as e:
            logging.error(f"启动监控失败: {str(e)}")
            self.stop_monitoring(directory)
            return False

    def stop_monitoring(self, directory: str = None):
        """停止监控指定目录或所有目录"""
        if directory:
            if directory in self.monitor_processes:
                try:
                    # 设置停止事件
                    if directory in self.stop_events:
                        self.stop_events[directory].set()
                    
                    # 等待进程结束
                    process = self.monitor_processes[directory]
                    process.join(timeout=5)
                    
                    # 如果进程还在运行，强制终止
                    if process.is_alive():
                        process.terminate()
                        process.join(timeout=1)
                    
                    # 清理资源
                    if directory in self.monitor_processes:
                        del self.monitor_processes[directory]
                    if directory in self.stop_events:
                        del self.stop_events[directory]
                    if directory in self.log_queues:
                        del self.log_queues[directory]
                    
                    logging.info(f"成功停止监控目录: {directory}")
                    
                except Exception as e:
                    logging.error(f"停止监控失败: {str(e)}")
        else:
            # 停止所有监控
            for dir_path in list(self.monitor_processes.keys()):
                self.stop_monitoring(dir_path)
            # 确保清理所有资源
            self.monitor_processes.clear()
            self.stop_events.clear()
            self.log_queues.clear()

    def is_monitoring(self, directory: str) -> bool:
        """检查指定目录是否正在被监控"""
        return directory in self.monitor_processes and self.monitor_processes[directory].is_alive()

    def get_monitored_directories(self) -> Set[str]:
        """获取所有正在监控的目录"""
        return set(self.monitor_processes.keys())

# Windows平台支持
if sys.platform.startswith('win'):
    freeze_support()
