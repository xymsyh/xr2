"""纯文本判断、规范化与语音选择。"""
import re

语音 = "zh-CN-XiaoxiaoNeural"

纯英文语音 = "en-CA-ClaraNeural"

_代码关键词 = re.compile(
    r"\b("
    r"def|class|import|from|return|function|var|let|const|public|private|protected|"
    r"static|void|int|float|double|bool|boolean|string|True|False|None|null|nil|"
    r"undefined|print|console\.log|if|else|elif|for|while|try|except|catch|finally|"
    r"switch|case|break|continue|new|this|self|async|await|lambda|yield|package|"
    r"namespace|using|include|struct|enum|interface|extends|implements|throw|throws"
    r")\b"
)

_代码符号 = re.compile(r"[{};]|=>|==|!=|&&|\|\||::|->|#include|<\?php|\+\+|--|\bdef\s+\w+\s*\(")

def 含中文(文本):
    return bool(re.search(r"[\u4e00-\u9fff]", 文本))


def 是纯英文(文本):
    """文本至少含一个英文字母，且所有字母都是 ASCII 英文字母。"""
    字母 = [字符 for 字符 in 文本 if 字符.isalpha()]
    return bool(字母) and all("a" <= 字符.lower() <= "z" for 字符 in 字母)


def 选择朗读语音(文本):
    return 纯英文语音 if 是纯英文(文本) else 语音


def 是否是代码(文本):
    """粗略判断选中内容是否为代码片段，宁可漏判也不误伤正常短语/单词"""
    if not 文本 or not 文本.strip():
        return False

    行列表 = 文本.splitlines()

    # 把没有缩进的换行统一替换成空格再判断，避免网页折行/自动换行干扰后续检测
    拼接文本 = re.sub(r"\s*\n\s*", " ", 文本).strip()

    符号命中数 = len(_代码符号.findall(拼接文本))
    关键词命中 = bool(_代码关键词.search(拼接文本))

    # 1) 出现缩进行 且 同时伴随真正的代码符号，才是代码块的强特征；
    #    这里不用"关键词命中"来佐证——this/for/new/case/try/let 等
    #    关键词本身也是极常见的英语单词，配合"关键词+缩进"很容易把
    #    普通英文段落误判为代码，只有实打实的代码符号才够可靠
    if len(行列表) > 1:
        缩进行数 = sum(1 for 行 in 行列表 if 行[:1] in (" ", "\t") and 行.strip())
        if 缩进行数 >= 1 and 符号命中数 >= 1:
            return True

    # 2) 出现两个及以上明显的代码符号
    if 符号命中数 >= 2:
        return True

    # 3) 关键词 + 至少一个代码符号，才判定为代码，避免把普通单词误判
    if 关键词命中 and 符号命中数 >= 1:
        return True

    # 4) 非字母数字/空白/中文字符占比过高，且数量不少，通常是代码或表达式
    非普通字符数 = len(re.findall(r"[^\w\s\u4e00-\u9fff]", 拼接文本))
    if len(拼接文本) > 0 and 非普通字符数 >= 3 and 非普通字符数 / len(拼接文本) > 0.15:
        return True

    return False


def 拆分驼峰(文本):
    """WindowsSelectorEventLoopPolicy -> Windows Selector Event Loop Policy"""
    # 小写/数字 与 紧跟的大写字母之间加空格
    文本 = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", 文本)
    # 连续大写后紧跟"大写+小写"的情况（如 HTTPServer -> HTTP Server）
    文本 = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", 文本)
    return 文本


def 预处理翻译文本(文本):
    文本 = 文本.replace("_", " ")   # 下划线替换为空格
    文本 = 拆分驼峰(文本)            # 驼峰命名拆分为空格分隔的单词
    文本 = re.sub(r"\s+", " ", 文本).strip()  # 合并多余空白
    return 文本


def 替换下划线为空格(文本):
    return 文本.replace("_", " ")
