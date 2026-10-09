"""Optional explicit network adapter. No key persistence; no redirects."""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from .evidence import InvalidInput, required_string, sha
from .io import load_json, json_bytes
from . import __version__

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class Provider:
    def __init__(self, config_path, cache_dir=None):
        config, _ = load_json(config_path)
        if set(config) - {'endpoint', 'model', 'api_key_env', 'timeout', 'max_output_tokens'}:
            raise InvalidInput('配置含未知字段；密钥只能通过api_key_env指定的环境变量传入')
        self.endpoint = config.get('endpoint', '')
        required_string(self.endpoint, 'endpoint')
        parsed = urllib.parse.urlsplit(self.endpoint)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise InvalidInput('endpoint不能含账号、查询参数或fragment')
        if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1', '::1')):
            raise InvalidInput('远程endpoint必须用HTTPS；HTTP只允许本机回环地址')
        if not parsed.hostname:
            raise InvalidInput('endpoint缺少主机')
        self.model = config.get('model')
        self.key_env = config.get('api_key_env', 'BOOK_DISTILLER_API_KEY')
        if not isinstance(self.model, str) or not self.model.strip():
            raise InvalidInput('配置缺少model')
        if not isinstance(self.key_env, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', self.key_env):
            raise InvalidInput('api_key_env必须是环境变量名')
        self.timeout = config.get('timeout', 120)
        self.max_tokens = config.get('max_output_tokens', 8192)
        if not isinstance(self.timeout, (int, float)) or not 1 <= self.timeout <= 900:
            raise InvalidInput('timeout范围为1–900秒')
        if not isinstance(self.max_tokens, int) or not 1 <= self.max_tokens <= 65536:
            raise InvalidInput('max_output_tokens范围为1–65536')
        self.cache_dir = Path(cache_dir) if cache_dir else None

    def complete(self, instruction, material):
        body = {'model': self.model, 'messages': [
            {'role': 'system', 'content': instruction},
            {'role': 'user', 'content': json.dumps(material, ensure_ascii=False)}],
            'temperature': 0.3, 'max_tokens': self.max_tokens}
        key = sha(json_bytes({'endpoint': self.endpoint, 'request': body}))
        cache = self.cache_dir / (key + '.json') if self.cache_dir else None
        if cache and cache.exists():
            result, _ = load_json(cache)
            return result  # caller always validates against current source
        secret = os.environ.get(self.key_env)
        if not secret:
            raise InvalidInput('缺少配置指定的API密钥环境变量')
        request = urllib.request.Request(self.endpoint, data=json_bytes(body), headers={
            'Authorization': 'Bearer ' + secret, 'Content-Type': 'application/json',
            'User-Agent': 'BookDistiller/' + __version__})
        try:
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=self.timeout) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise InvalidInput('模型响应超过8MiB限制')
            payload = json.loads(raw)
            content = payload['choices'][0]['message']['content']
            if not isinstance(content, str):
                raise ValueError()
            content = content.strip()
            if content.startswith('```json') and content.endswith('```'):
                content = content[7:-3].strip()
            result = json.loads(content)
            if not isinstance(result, dict):
                raise ValueError()
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            raise InvalidInput(f'模型HTTP错误 {status}；未写正式输出，未回显服务端正文') from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise InvalidInput('模型连接失败或超时；未写正式输出') from None
        except (ValueError, KeyError, IndexError, TypeError):
            raise InvalidInput('模型没有返回约定的JSON对象；未写正式输出') from None
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            try:
                with cache.open('xb') as stream:
                    stream.write(json_bytes(result))
            except FileExistsError:
                # Another process completed the same request. Never overwrite its cache.
                existing, _ = load_json(cache)
                if existing != result:
                    raise InvalidInput('同一请求的缓存出现并发差异；保留双方状态，未写正式输出') from None
        return result
