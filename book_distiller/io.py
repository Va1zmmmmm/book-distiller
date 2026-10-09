import json
import re
from pathlib import Path
from .evidence import InvalidInput, sha

def load_json(path):
    raw = Path(path).read_bytes()
    try:
        data = json.loads(raw.decode('utf-8-sig'))
    except (ValueError, UnicodeError):
        raise InvalidInput('输入不是有效UTF-8 JSON') from None
    if not isinstance(data, dict):
        raise InvalidInput('JSON顶层必须是对象')
    return data, sha(raw)

def safe_id(value, field='id'):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', value):
        raise InvalidInput(f'{field} 只允许1–64个ASCII字母、数字、下划线或连字符')
    if value.upper() in {'CON', 'PRN', 'AUX', 'NUL'} or re.fullmatch(r'(COM|LPT)[1-9]', value.upper()):
        raise InvalidInput(f'{field}不能使用Windows设备保留名')
    return value

def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')

def write_bundle(out, files):
    """Only creates a new output directory. Existing/manual files never overwritten."""
    out = Path(out)
    # Validate all names before reserving the directory or writing any output.
    for name in files:
        p = Path(name)
        if p.is_absolute() or '..' in p.parts:
            raise InvalidInput('输出文件名越界')
    try:
        out.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise InvalidInput('输出目录已存在；请选一个新目录，避免覆盖手工内容') from None
    for name, data in files.items():
        p = out / name
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('xb') as stream:
            stream.write(data if isinstance(data, bytes) else data.encode('utf-8'))
    return out

def checked_read(root, relative, expected):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise InvalidInput('材料路径越界')
    raw = path.read_bytes()
    if sha(raw) != expected:
        raise InvalidInput('材料已变化，重新准备或校验后再使用')
    return raw
