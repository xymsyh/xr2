"""翻译缓存、学习记录和语音缓存持久化。"""
import os
import json
import hashlib
from datetime import datetime
from .paths import 翻译缓存文件, 翻译记录文件, 语音缓存目录, 语音缓存索引文件
from .text import 语音


def 加载翻译缓存():
    try:
        with open(翻译缓存文件, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def 保存翻译缓存():
    try:
        with open(翻译缓存文件, "w", encoding="utf-8") as f:
            json.dump(翻译缓存, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("保存翻译缓存失败：", e)


def 缓存键(待翻译文本):
    # 忽略大小写，减少因大小写不同造成的缓存未命中
    return 待翻译文本.strip().lower()


def 加载翻译记录():
    try:
        with open(翻译记录文件, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def 保存翻译记录():
    try:
        with open(翻译记录文件, "w", encoding="utf-8") as f:
            json.dump(翻译记录, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("保存翻译记录失败：", e)


def 更新翻译记录(原文, 处理后文本, 译文, 类型="文本", 词头=None, 来源=None):
    """相同内容（按处理后文本归一化）只保留一条记录，累加次数，并更新为最新时间/日期"""
    键 = 缓存键(处理后文本)
    现在 = datetime.now()
    时间字符串 = 现在.strftime("%Y-%m-%d %H:%M:%S")
    日期字符串 = 现在.strftime("%Y-%m-%d")

    已有 = 翻译记录.get(键)
    if 已有 is None:
        翻译记录[键] = {
            "原文": 原文,
            "送去翻译的文本": 处理后文本,
            "译文": 译文,
            "类型": 类型,
            "首次时间": 时间字符串,
            "最新时间": 时间字符串,
            "日期": 日期字符串,
            "次数": 1,
        }
    else:
        已有["原文"] = 原文
        已有["送去翻译的文本"] = 处理后文本
        已有["译文"] = 译文
        已有["类型"] = 类型
        已有["最新时间"] = 时间字符串
        已有["日期"] = 日期字符串
        已有["次数"] = 已有.get("次数", 1) + 1

    if 词头:
        翻译记录[键]["词头"] = 词头
    if 来源:
        翻译记录[键]["来源"] = 来源

    保存翻译记录()


def 加载语音缓存索引():
    try:
        with open(语音缓存索引文件, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def 保存语音缓存索引():
    try:
        with open(语音缓存索引文件, "w", encoding="utf-8") as f:
            json.dump(语音缓存索引, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("保存语音缓存索引失败：", e)


def 语音缓存键(文本, 使用语音=None):
    # 忽略大小写和首尾空白，"hello" / "Hello " 视为同一条缓存
    键 = 文本.strip().lower()
    # 默认语音沿用旧缓存键；纯英文语音带上语音名，避免误用以前由晓晓生成的英文音频。
    if 使用语音 and 使用语音 != 语音:
        return f"{使用语音}\n{键}"
    return 键


def 语音缓存文件路径(键):
    # 文本本身可能含有 Windows 文件名不支持的字符，所以用哈希值做文件名
    文件名 = hashlib.md5(键.encode("utf-8")).hexdigest() + ".mp3"
    return os.path.join(语音缓存目录, 文件名), 文件名


def _写入语音缓存(键, 文件名, 缓存路径, 文本, 音频字节):
    """在线程池里执行的同步写盘逻辑，供 run_in_executor 调用，不阻塞事件循环/播放"""
    try:
        with open(缓存路径, "wb") as f:
            f.write(音频字节)

        已有 = 语音缓存索引.get(键, {})
        语音缓存索引[键] = {
            "文本": 文本,
            "文件名": 文件名,
            "次数": 已有.get("次数", 0) + 1,
        }
        保存语音缓存索引()
    except Exception as e:
        print("保存语音缓存失败：", e)

翻译缓存 = 加载翻译缓存()
翻译记录 = 加载翻译记录()
语音缓存索引 = 加载语音缓存索引()
