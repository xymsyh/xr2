"""所有路径以项目位置为准，与当前工作目录无关。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
RUNTIME_DIR = ROOT / "runtime"
CACHE_DIR = RUNTIME_DIR / "cache"
DATA_DIR = RUNTIME_DIR / "data"
LOG_DIR = RUNTIME_DIR / "logs"
配置路径 = CONFIG_DIR / "配置.ini"
配置示例路径 = CONFIG_DIR / "配置示例.ini"
数据库路径 = ROOT / "data" / "dictionary.sqlite3"
位置记录文件 = DATA_DIR / "翻译窗口位置.json"
翻译记录文件 = DATA_DIR / "翻译记录.json"
翻译缓存文件 = CACHE_DIR / "翻译缓存.json"
语音缓存目录 = CACHE_DIR / "audio"
语音缓存索引文件 = 语音缓存目录 / "索引.json"
预渲染日志文件 = LOG_DIR / "预渲染.md"


def 初始化目录():
    for directory in (CONFIG_DIR, DATA_DIR, LOG_DIR, 语音缓存目录):
        directory.mkdir(parents=True, exist_ok=True)
