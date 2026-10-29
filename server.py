import json, os, secrets, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent
# Local configuration is ignored by Git. Environment variables take precedence.
config = ROOT / '.env'
if config.exists():
    for line in config.read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())
TOKEN = secrets.token_urlsafe(32)
SYSTEM = '''你是“心港”，一个明确告知用户自己是 AI 的中文情绪陪伴助手。认真回应具体经历，语气自然、简短、有温度，不评判、不说教。先理解，再根据用户意愿一起梳理或提出一个小步骤。每次最多一个自然的追问，避免重复套话。用户只想倾诉时不强推建议。不诊断精神疾病、不提供药物或治疗指令、不保证疗效。不虚构记忆，不鼓励排他依赖，支持现实中的人际联系。遇到自伤、自杀或伤害他人的表达，认真询问当前是否有立即危险，鼓励联系可信任的人和当地紧急服务，不编造热线号码；不能仅凭情绪标签判断风险。'''

def reply(messages, mode):
    key = os.environ.get('MODEL_API_KEY', '')
    model = os.environ.get('MODEL_NAME', '')
    base = os.environ.get('MODEL_BASE_URL', '').rstrip('/')
    if not key or not model or not base:
        raise ValueError('请先在本地 .env 配置模型服务地址、模型名称和 API 密钥。')
    if not base.startswith('https://') and not base.startswith('http://localhost:') and not base.startswith('http://127.0.0.1:'):
        raise ValueError('模型服务必须使用 HTTPS，本地服务除外。')
    payload = {'model': model, 'messages': [{'role': 'system', 'content': SYSTEM + '\n用户当前偏好：' + mode}] + messages}
    req = urllib.request.Request(base + '/chat/completions', data=json.dumps(payload).encode(), headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as response:
        answer = json.load(response)['choices'][0]['message']['content']
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError('empty model response')
    return answer

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Never log conversation bodies or credentials.
    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        if self.path == '/api/session':
            return self.send_json(200, {'token': TOKEN, 'configured': all(os.environ.get(k) for k in ['MODEL_API_KEY', 'MODEL_NAME', 'MODEL_BASE_URL'])})
        if self.path not in ['/', '/index.html']:
            return self.send_json(404, {'error': '页面不存在'})
        body = (ROOT / 'static/index.html').read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)
    def do_POST(self):
        if self.path != '/api/chat':
            return self.send_json(404, {'error': '接口不存在'})
        if self.headers.get('X-Session-Token') != TOKEN:
            return self.send_json(403, {'error': '请刷新页面后重试'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size <= 0 or size > 150000:
                return self.send_json(413, {'error': '对话过长，请开启新对话'})
            data = json.loads(self.rfile.read(size))
            messages = data['messages']
            if not isinstance(messages, list) or not 1 <= len(messages) <= 60:
                raise ValueError('最多支持 30 轮对话，请开启新对话。')
            for i, item in enumerate(messages):
                if item.get('role') != ('user' if i % 2 == 0 else 'assistant') or not isinstance(item.get('content'), str) or not 1 <= len(item['content'].strip()) <= 4000:
                    raise ValueError('消息格式错误，单条消息最多 4000 字。')
            if messages[-1]['role'] != 'user':
                raise ValueError('最后一条消息必须来自用户。')
            mode = data.get('mode', '倾诉')
            if mode not in ['倾诉', '梳理', '想办法']:
                raise ValueError('未知聊天模式')
            answer = reply(messages, mode)
            return self.send_json(200, {'reply': answer})
        except (ValueError, KeyError, TypeError, AttributeError):
            return self.send_json(400, {'error': '请检查消息格式和 .env 模型配置；最多 30 轮，每条最多 4000 字。'})
        except Exception:
            return self.send_json(502, {'error': '模型服务暂时无法连接，请检查地址、密钥、模型名和网络后重试。'})

if __name__ == '__main__':
    print('心港本地版：http://127.0.0.1:8765 （Ctrl+C 停止）')
    ThreadingHTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
