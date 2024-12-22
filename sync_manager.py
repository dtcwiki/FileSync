import os
import sys
import time
import socket
import logging
import paramiko
import ftplib
import requests
import concurrent.futures
from typing import Optional, Callable, List, Tuple, Dict, Any
from threading import Lock
from queue import Queue
from urllib.parse import urljoin

class SyncManager:
    """同步管理器类，负责处理与远程服务器的文件同步"""
    
    def __init__(self):
        self.connections = {}
        self.connection_locks = {}
        
    def create_connection(self, task_id: str, config: dict) -> bool:
        """创建与远程服务器的连接"""
        if task_id in self.connections:
            logging.error(f"任务 {task_id} 已经存在，无法创建连接")
            return False
        
        try:
            protocol = config['protocol']
            if protocol == 'SFTP':
                return self._create_sftp_connection(task_id, config)
            elif protocol == 'FTP':
                return self._create_ftp_connection(task_id, config)
            elif protocol == 'WebDAV':
                return self._create_webdav_connection(task_id, config)
            else:
                logging.error(f"不支持的协议: {protocol}")
                return False
        except Exception as e:
            logging.error(f"创建连接失败: {str(e)}，配置: {config}")
            return False

    def _create_sftp_connection(self, task_id: str, config: dict) -> bool:
        """创建SFTP连接"""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            connect_kwargs = {
                'hostname': config['host'],
                'port': config.get('port', 22),
                'username': config['username'],
            }
            
            # 根据认证方式选择密码或密钥文件
            if config.get('use_key_auth', False):
                key_path = config['key_path']
                if os.path.exists(key_path):
                    private_key = paramiko.RSAKey.from_private_key_file(key_path)
                    connect_kwargs['pkey'] = private_key
                else:
                    logging.error(f"密钥文件不存在: {key_path}")
                    return False
            else:
                connect_kwargs['password'] = config['password']
            
            ssh.connect(**connect_kwargs)
            sftp = ssh.open_sftp()
            
            self.connections[task_id] = {
                'type': 'SFTP',
                'ssh': ssh,
                'sftp': sftp,
                'config': config
            }
            self.connection_locks[task_id] = Lock()
            
            return True
            
        except Exception as e:
            logging.error(f"创建SFTP连接失败: {str(e)}")
            return False

    def _create_ftp_connection(self, task_id: str, config: dict) -> bool:
        """创建FTP连接，包含重试机制"""
        max_retries = 3
        retry_count = 0
        retry_delay = 2  # 重试延迟（秒）
        
        while retry_count < max_retries:
            try:
                # 创建FTP实例
                ftp = ftplib.FTP()
                ftp.set_debuglevel(0)
                ftp.encoding = 'utf-8'
                
                # 连接服务器
                logging.info(f"正在连接FTP服务器: {config['host']}:{config.get('port', 21)}")
                ftp.connect(
                    host=config['host'],
                    port=config.get('port', 21),
                    timeout=30
                )
                
                # 登录
                logging.info("正在登录FTP服务器")
                ftp.login(
                    user=config['username'],
                    passwd=config['password']
                )
                
                # 设置被动模式
                ftp.set_pasv(True)
                
                # 设置socket选项
                if ftp.sock is not None:
                    # 启用TCP保活
                    ftp.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                    # 设置超时
                    ftp.sock.settimeout(30)
                
                # 测试连接
                ftp.voidcmd('NOOP')
                
                # 获取欢迎信息
                welcome = ftp.getwelcome()
                logging.info(f"FTP服务器欢迎信息: {welcome}")
                
                # 保存连接信息
                self.connections[task_id] = {
                    'type': 'FTP',
                    'ftp': ftp,
                    'config': config,
                    'pool': concurrent.futures.ThreadPoolExecutor(max_workers=4)  # 添加线程池
                }
                self.connection_locks[task_id] = Lock()
                
                logging.info("FTP连接创建成功")
                return True
                
            except (socket.error, ftplib.error_temp) as e:
                retry_count += 1
                if retry_count < max_retries:
                    logging.warning(f"FTP连接失败，{retry_delay}秒后重试 ({retry_count}/{max_retries}): {str(e)}")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                else:
                    logging.error(f"FTP连接失败，已达到最大重试次数: {str(e)}")
                    return False
            except Exception as e:
                logging.error(f"创建FTP连接失败: {str(e)}")
                return False

    def _get_basic_auth(self, username: str, password: str) -> str:
        """生成Basic认证头"""
        import base64
        auth_str = f"{username}:{password}"
        auth_bytes = auth_str.encode('utf-8')
        return base64.b64encode(auth_bytes).decode('utf-8')

    def _create_webdav_connection(self, task_id: str, config: dict) -> bool:
        """创建WebDAV连接"""
        max_retries = 3
        retry_count = 0
        retry_delay = 1  # 初始重试延迟（秒）
        
        while retry_count <= max_retries:
            try:
                # 创建Session对象以复用连接
                session = requests.Session()
                
                # 配置连接池
                adapter = requests.adapters.HTTPAdapter(
                    pool_connections=10,    # 连接池大小
                    pool_maxsize=10,        # 最大连接数
                    max_retries=3,          # 连接级别的重试
                    pool_block=False        # 连接池满时不阻塞
                )
                session.mount('http://', adapter)
                session.mount('https://', adapter)
                
                # 设置认证
                session.auth = (config['username'], config['password'])
                
                # 设置通用请求头
                session.headers.update({
                    'User-Agent': 'WebDAV Client',
                    'Accept': '*/*',
                    'Content-Type': 'application/xml',
                    'Connection': 'keep-alive',
                    'Keep-Alive': 'timeout=60, max=1000',
                    'Authorization': f'Basic {self._get_basic_auth(config["username"], config["password"])}',
                })
                
                # 使用用户提供的WebDAV URL
                webdav_url = config['host'].rstrip('/')
                logging.info(f"使用WebDAV URL: {webdav_url}")
                
                # 验证连接
                response = session.request(
                    'PROPFIND',
                    webdav_url,
                    headers={
                        'Depth': '0',
                        'Prefer': 'return-minimal',
                    },
                    timeout=30  # 添加超时设置
                )
                response.raise_for_status()
                
                # 创建线程池
                pool = concurrent.futures.ThreadPoolExecutor(
                    max_workers=4,  # 限制并发连接数
                    thread_name_prefix=f'WebDAV-{task_id}'
                )
                
                self.connections[task_id] = {
                    'type': 'WebDAV',
                    'session': session,
                    'config': config,
                    'pool': pool,
                    'retry_count': 0,
                    'max_retries': 3
                }
                self.connection_locks[task_id] = Lock()
                
                return True
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:  # 未授权错误
                    retry_count += 1
                    if retry_count <= max_retries:
                        wait_time = retry_delay * (2 ** (retry_count - 1))  # 指数退避
                        logging.warning(f"WebDAV连接认证失败，{wait_time}秒后重试 ({retry_count}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                logging.error(f"WebDAV连接失败: {str(e)}")
                return False
            except Exception as e:
                logging.error(f"创建WebDAV连接失败: {str(e)}")
                return False
        
        return False

    def close_connection(self, task_id: str):
        """关闭与远程服务器的连接"""
        if task_id in self.connections:
            try:
                conn = self.connections[task_id]
                if conn['type'] == 'SFTP':
                    conn['sftp'].close()
                    conn['ssh'].close()
                elif conn['type'] == 'FTP':
                    try:
                        # 关闭线程池
                        if 'pool' in conn:
                            conn['pool'].shutdown(wait=True)
                        # 关闭FTP连接
                        conn['ftp'].quit()
                    except:
                        try:
                            conn['ftp'].close()
                        except:
                            pass
                elif conn['type'] == 'WebDAV':
                    try:
                        # 关闭线程池
                        if 'pool' in conn:
                            conn['pool'].shutdown(wait=True)
                    except Exception as e:
                        logging.error(f"关闭WebDAV线程池失败: {str(e)}")
                
                del self.connections[task_id]
                del self.connection_locks[task_id]
                
            except Exception as e:
                logging.error(f"关闭连接失败: {str(e)}")

    def sync_file(self, task_id: str, local_path: str, remote_path: str, 
                  operation: str = 'upload') -> bool:
        """同步单个文件，使用线程池进行并发同步"""
        if task_id not in self.connections:
            logging.error(f"任务 {task_id} 未建立连接")
            return False
            
        conn = self.connections[task_id]
        lock = self.connection_locks[task_id]
        
        try:
            if conn['type'] == 'FTP':
                # 使用线程池进行FTP同步
                future = conn['pool'].submit(
                    self._sync_file_ftp,
                    conn['ftp'],
                    local_path,
                    remote_path,
                    operation,
                    conn['config']
                )
                return future.result(timeout=60)  # 设置超时时间
            else:
                # 其他协议使用原有的同步方式
                with lock:
                    if conn['type'] == 'SFTP':
                        return self._sync_file_sftp(conn['sftp'], local_path, 
                                                  remote_path, operation)
                    elif conn['type'] == 'WebDAV':
                        return self._sync_file_webdav(conn['session'], local_path, 
                                                    remote_path, operation, task_id)
                    return False
                
        except concurrent.futures.TimeoutError:
            logging.error(f"同步文件超时: {local_path} -> {remote_path}")
            return False
        except Exception as e:
            logging.error(f"同步文件失败: {str(e)}")
            return False

    def _sync_file_sftp(self, sftp, local_path: str, remote_path: str, 
                       operation: str) -> bool:
        """通过SFTP同步文件"""
        try:
            if operation == 'upload':
                # 确保远程目录存在
                remote_dir = os.path.dirname(remote_path)
                try:
                    sftp.stat(remote_dir)
                except FileNotFoundError:
                    self._mkdir_p_sftp(sftp, remote_dir)
                
                sftp.put(local_path, remote_path)
            elif operation == 'download':
                # 确保本地目录存在
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                sftp.get(remote_path, local_path)
            elif operation == 'delete':
                sftp.remove(remote_path)
            return True
            
        except Exception as e:
            logging.error(f"SFTP同步失败: {str(e)}")
            return False

    def _sync_file_ftp(self, ftp, local_path: str, remote_path: str, 
                      operation: str, config: dict) -> bool:
        """通过FTP同步文件"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 检查连接状态
                try:
                    ftp.voidcmd('NOOP')
                except:
                    logging.warning("FTP连接已断开，尝试重新连接")
                    self._reconnect_ftp(ftp, config)
                
                # 规范化路径
                remote_path = remote_path.replace('\\', '/')
                if not remote_path.startswith('/'):
                    remote_path = '/' + remote_path
                    
                if operation == 'upload':
                    # 确保远程目录存在
                    remote_dir = os.path.dirname(remote_path)
                    self._mkdir_p_ftp(ftp, remote_dir)
                    
                    # 设置二进制传输模式
                    ftp.voidcmd('TYPE I')
                    
                    # 上传文件
                    with open(local_path, 'rb') as f:
                        try:
                            ftp.storbinary(f'STOR {remote_path}', f, blocksize=8192)
                            logging.info(f"文件上传成功: {local_path} -> {remote_path}")
                            return True
                        except ftplib.error_perm as e:
                            logging.error(f"FTP上传权限错误: {str(e)}")
                            return False
                            
                elif operation == 'download':
                    # 确保本地目录存在
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    
                    # 设置二进制传输模式
                    ftp.voidcmd('TYPE I')
                    
                    # 下载文件
                    with open(local_path, 'wb') as f:
                        try:
                            ftp.retrbinary(f'RETR {remote_path}', f.write, blocksize=8192)
                            logging.info(f"文件下载成功: {remote_path} -> {local_path}")
                            return True
                        except ftplib.error_perm as e:
                            logging.error(f"FTP下载权限错误: {str(e)}")
                            return False
                            
                elif operation == 'delete':
                    try:
                        ftp.delete(remote_path)
                        logging.info(f"文件删除成功: {remote_path}")
                        return True
                    except ftplib.error_perm as e:
                        logging.error(f"FTP删除权限错误: {str(e)}")
                        return False
                    
                return False
                
            except (ftplib.error_temp, socket.error) as e:
                retry_count += 1
                if retry_count < max_retries:
                    logging.warning(f"FTP操作失败，正在重试 ({retry_count}/{max_retries}): {str(e)}")
                    time.sleep(1)
                else:
                    logging.error(f"FTP操作失败，已达到最大重试次数: {str(e)}")
                    return False
            except Exception as e:
                logging.error(f"FTP同步失败: {str(e)}")
                return False
        
        return False

    def _sync_file_webdav(self, session, local_path: str, remote_path: str, 
                         operation: str, task_id: str) -> bool:
        """通过WebDAV同步文件"""
        conn = self.connections[task_id]
        max_retries = conn['max_retries']
        retry_count = 0
        retry_delay = 1  # 初始重试延迟（秒）

        while retry_count <= max_retries:
            try:
                base_url = conn['config']['host']
                # 确保路径正确编码
                encoded_path = '/'.join(requests.utils.quote(p) for p in remote_path.split('/'))
                url = urljoin(base_url + '/', encoded_path.lstrip('/'))
                logging.info(f"WebDAV操作URL: {url}")
                
                if operation == 'upload':
                    # 确保远程目录存在
                    remote_dir = os.path.dirname(remote_path)
                    if remote_dir:
                        self._ensure_webdav_dir(session, base_url, remote_dir)
                    
                    # 使用线程池上传文件
                    future = conn['pool'].submit(self._webdav_upload_file,
                                              session, url, local_path)
                    result = future.result(timeout=60)  # 设置超时时间
                    if not result:
                        raise Exception("上传失败")
                        
                elif operation == 'download':
                    # 确保本地目录存在
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    
                    # 使用线程池下载文件
                    future = conn['pool'].submit(self._webdav_download_file,
                                              session, url, local_path)
                    result = future.result(timeout=60)
                    if not result:
                        raise Exception("下载失败")
                        
                elif operation == 'delete':
                    # 使用线程池删除文件
                    future = conn['pool'].submit(self._webdav_delete_file,
                                              session, url)
                    result = future.result(timeout=30)
                    if not result:
                        raise Exception("删除失败")
                
                return True
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401:  # 未授权错误
                    retry_count += 1
                    if retry_count <= max_retries:
                        wait_time = retry_delay * (2 ** (retry_count - 1))  # 指数退避
                        logging.warning(f"WebDAV认证失败，{wait_time}秒后重试 ({retry_count}/{max_retries})")
                        time.sleep(wait_time)
                        # 重新创建session
                        session = requests.Session()
                        session.auth = (conn['config']['username'], conn['config']['password'])
                        session.headers.update({
                            'User-Agent': 'WebDAV Client',
                            'Accept': '*/*',
                            'Content-Type': 'application/xml',
                        })
                        conn['session'] = session
                        continue
                logging.error(f"WebDAV操作失败: {str(e)}")
                return False
                
            except Exception as e:
                logging.error(f"WebDAV同步失败: {str(e)}")
                return False
                
        return False

    def _webdav_upload_file(self, session, url: str, local_path: str) -> bool:
        """WebDAV文件上传处理"""
        try:
            with open(local_path, 'rb') as f:
                headers = {
                    'Content-Type': 'application/octet-stream',
                    'Accept': '*/*',
                    'Connection': 'keep-alive',
                    'Keep-Alive': 'timeout=60, max=1000'
                }
                response = session.put(url, data=f, headers=headers, timeout=60)
                
                if response.status_code == 401:  # 未授权错误，尝试刷新认证头
                    auth_header = session.headers.get('Authorization')
                    if auth_header:
                        headers['Authorization'] = auth_header
                        response = session.put(url, data=f, headers=headers, timeout=60)
                
                if response.status_code not in [200, 201, 204]:
                    logging.error(f"WebDAV上传失败: {url}, 状态码: {response.status_code}")
                    if response.text:
                        logging.error(f"错误详情: {response.text}")
                    return False
            return True
        except Exception as e:
            logging.error(f"WebDAV上传失败: {str(e)}")
            return False

    def _webdav_download_file(self, session, url: str, local_path: str) -> bool:
        """WebDAV文件下载处理"""
        try:
            headers = {
                'Accept': '*/*',
                'Connection': 'keep-alive',
                'Keep-Alive': 'timeout=60, max=1000'
            }
            response = session.get(url, headers=headers, timeout=60, stream=True)
            
            if response.status_code == 401:  # 未授权错误，尝试刷新认证头
                auth_header = session.headers.get('Authorization')
                if auth_header:
                    headers['Authorization'] = auth_header
                    response = session.get(url, headers=headers, timeout=60, stream=True)
            
            if response.status_code != 200:
                logging.error(f"WebDAV下载失败: {url}, 状态码: {response.status_code}")
                if response.text:
                    logging.error(f"错误详情: {response.text}")
                return False
            
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        except Exception as e:
            logging.error(f"WebDAV下载失败: {str(e)}")
            return False

    def _webdav_delete_file(self, session, url: str) -> bool:
        """WebDAV文件删除处理"""
        try:
            headers = {
                'Accept': '*/*',
                'Connection': 'keep-alive',
                'Keep-Alive': 'timeout=60, max=1000'
            }
            response = session.delete(url, headers=headers, timeout=30)
            
            if response.status_code == 401:  # 未授权错误，尝试刷新认证头
                auth_header = session.headers.get('Authorization')
                if auth_header:
                    headers['Authorization'] = auth_header
                    response = session.delete(url, headers=headers, timeout=30)
            
            if response.status_code not in [200, 204]:
                logging.error(f"WebDAV删除失败: {url}, 状态码: {response.status_code}")
                if response.text:
                    logging.error(f"错误详情: {response.text}")
                return False
            return True
        except Exception as e:
            logging.error(f"WebDAV删除失败: {str(e)}")
            return False
            
    def _ensure_webdav_dir(self, session, base_url: str, remote_dir: str):
        """确保WebDAV远程目录存在"""
        if not remote_dir:
            return
            
        parts = remote_dir.split('/')
        current_path = ''
        
        for part in parts:
            if not part:
                continue
                
            current_path += '/' + requests.utils.quote(part)
            url = urljoin(base_url, current_path.lstrip('/'))
            logging.info(f"检查WebDAV目录: {url}")
            
            max_retries = 3
            retry_count = 0
            retry_delay = 1  # 初始重试延迟（秒）
            
            while retry_count <= max_retries:
                try:
                    # 检查目录是否存在
                    headers = {
                        'Depth': '0',
                        'Prefer': 'return-minimal',
                        'Accept': 'application/xml, text/xml',
                        'Connection': 'keep-alive',
                        'Keep-Alive': 'timeout=60, max=1000'
                    }
                    
                    # 添加认证头
                    auth_header = session.headers.get('Authorization')
                    if auth_header:
                        headers['Authorization'] = auth_header
                    
                    response = session.request('PROPFIND', url, headers=headers, timeout=30)
                    
                    if response.status_code == 401:  # 未授权错误
                        retry_count += 1
                        if retry_count <= max_retries:
                            wait_time = retry_delay * (2 ** (retry_count - 1))  # 指数退避
                            logging.warning(f"WebDAV目录检查认证失败，{wait_time}秒后重试 ({retry_count}/{max_retries})")
                            time.sleep(wait_time)
                            continue
                        raise requests.exceptions.HTTPError("认证失败")
                    
                    if response.status_code == 404:
                        # 创建目录
                        headers = {
                            'Accept': '*/*',
                            'Connection': 'keep-alive',
                            'Keep-Alive': 'timeout=60, max=1000'
                        }
                        if auth_header:
                            headers['Authorization'] = auth_header
                            
                        response = session.request('MKCOL', url, headers=headers, timeout=30)
                        if response.status_code == 401:  # 未授权错误
                            retry_count += 1
                            if retry_count <= max_retries:
                                wait_time = retry_delay * (2 ** (retry_count - 1))
                                logging.warning(f"WebDAV目录创建认证失败，{wait_time}秒后重试 ({retry_count}/{max_retries})")
                                time.sleep(wait_time)
                                continue
                            raise requests.exceptions.HTTPError("认证失败")
                            
                        if response.status_code not in [200, 201]:
                            logging.error(f"创建WebDAV目录失败: {url}, 状态码: {response.status_code}")
                            if response.text:
                                logging.error(f"错误详情: {response.text}")
                            raise requests.exceptions.RequestException(f"创建目录失败: {response.status_code}")
                        logging.info(f"创建WebDAV目录: {url}")
                    elif response.status_code == 207:
                        # 目录已存在
                        break
                    else:
                        response.raise_for_status()
                    
                    # 如果执行到这里说明操作成功
                    break
                    
                except requests.exceptions.RequestException as e:
                    retry_count += 1
                    if retry_count <= max_retries:
                        wait_time = retry_delay * (2 ** (retry_count - 1))
                        logging.warning(f"WebDAV目录操作失败，{wait_time}秒后重试 ({retry_count}/{max_retries}): {str(e)}")
                        time.sleep(wait_time)
                    else:
                        logging.error(f"创建WebDAV目录失败: {url}, 错误: {str(e)}")
                        raise

    def _mkdir_p_sftp(self, sftp, remote_dir: str):
        """递归创建SFTP远程目录"""
        if remote_dir == '/':
            return
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            parent = os.path.dirname(remote_dir)
            if parent != remote_dir:
                self._mkdir_p_sftp(sftp, parent)
            sftp.mkdir(remote_dir)

    def _reconnect_ftp(self, ftp, config: dict):
        """重新连接FTP服务器"""
        try:
            # 尝试关闭旧连接
            try:
                ftp.close()
            except:
                pass
            
            # 重新连接
            ftp.connect(
                host=config['host'],
                port=config.get('port', 21),
                timeout=30
            )
            ftp.login(
                user=config['username'],
                passwd=config['password']
            )
            ftp.set_pasv(True)
            
            # 设置socket选项
            if ftp.sock is not None:
                ftp.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                ftp.sock.settimeout(30)
            
            logging.info("FTP重新连接成功")
            
        except Exception as e:
            logging.error(f"FTP重新连接失败: {str(e)}")
            raise
            
    def _mkdir_p_ftp(self, ftp, remote_dir: str):
        """递归创建FTP远程目录"""
        if remote_dir == '/':
            return
            
        # 规范化路径
        remote_dir = remote_dir.replace('\\', '/')
        if not remote_dir.startswith('/'):
            remote_dir = '/' + remote_dir
            
        # 分割路径
        parts = remote_dir.split('/')
        current_dir = ''
        
        for part in parts:
            if not part:
                continue
                
            current_dir += '/' + part
            try:
                ftp.cwd(current_dir)
            except ftplib.error_perm:
                try:
                    ftp.mkd(current_dir)
                    ftp.cwd(current_dir)
                    logging.info(f"创建远程目录: {current_dir}")
                except ftplib.error_perm as e:
                    if "550" not in str(e):  # 忽略目录已存在的错误
                        logging.error(f"创建目录失败: {current_dir}, 错误: {str(e)}")
                        raise

    def verify_remote_file(self, task_id: str, local_path: str, remote_path: str) -> bool:
        """验证远程文件是否存在且大小正确"""
        try:
            if task_id not in self.connections:
                return False
                
            conn = self.connections[task_id]
            if conn['type'] == 'SFTP':
                try:
                    remote_stat = conn['sftp'].stat(remote_path)
                    local_stat = os.stat(local_path)
                    return remote_stat.st_size == local_stat.st_size
                except FileNotFoundError:
                    return False
                    
            elif conn['type'] == 'FTP':
                try:
                    remote_size = conn['ftp'].size(remote_path)
                    local_size = os.path.getsize(local_path)
                    return remote_size == local_size
                except:
                    return False
                    
            elif conn['type'] == 'WebDAV':
                try:
                    base_url = conn['config']['host']
                    encoded_path = '/'.join(requests.utils.quote(p) for p in remote_path.split('/'))
                    url = urljoin(base_url + '/', encoded_path.lstrip('/'))
                    response = conn['session'].request('PROPFIND', url, headers={'Depth': '0'})
                    return response.status_code == 207
                except:
                    return False
                    
            return False
            
        except Exception as e:
            logging.error(f"验证远程文件失败: {str(e)}")
            return False
