"""跨模块共享的消息队列及启动后配置；导入时不注册按键或打开设备。"""
import queue
import threading
from .config import 初始化配置, 读取配置
from .paths import 初始化目录

翻译队列 = queue.Queue()
OCR请求队列 = queue.Queue()
OCR忙碌 = threading.Event()
按键映射 = {}
KEY = REGION = ENDPOINT = 音频发送地址 = ""
音频发送启用 = False


def 初始化运行环境():
    global KEY, REGION, ENDPOINT, 音频发送启用, 音频发送地址
    初始化目录()
    if 初始化配置():
        print("已生成 config/配置.ini；在线翻译需填写密钥后重启。")
    配置 = 读取配置()
    按键映射.update(配置["按键映射"])
    KEY = 配置["微软翻译API"]["密钥"]
    REGION = 配置["微软翻译API"]["区域"]
    ENDPOINT = 配置["微软翻译API"]["地址"]
    音频发送启用 = 配置["音频发送"]["启用"]
    音频发送地址 = 配置["音频发送"]["地址"]
