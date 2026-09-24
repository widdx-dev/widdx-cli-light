#!/usr/bin/env python3
"""WIDDX Nexus — Web UI with auto file creation and verification."""

import http.server
import socketserver
import json
import urllib.request
import os
import sys
import re
import subprocess
import tempfile
from pathlib import Path

PORT = 8080

def get_api_key():
    script_dir = Path(__file__).parent
    for env_path in [script_dir / '.env', Path('.env'), Path.cwd() / '.env']:
        if env_path.exists():
            content = env_path.read_bytes().decode('utf-8')
            for line in content.split('\n'):
                if '=' in line and not line.startswith('#'):
                    k, _, v = line.partition('=')
                    if k.strip() == 'DEEPSEEK_API_KEY':
                        return v.strip()
    return os.environ.get('DEEPSEEK_API_KEY', '')

def call_deepseek(messages, api_key):
    url = 'https://api.deepseek.com/chat/completions'
    body = json.dumps({
        'model': 'deepseek-chat',
        'messages': messages,
        'max_tokens': 4000,
        'stream': False,
    }).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data['choices'][0]['message']['content']
    except Exception as e:
        return f'Error: {e}'

def extract_and_save_files(content, target_dir=None):
    """Extract code blocks from AI response and save as files automatically."""
    if target_dir is None:
        target_dir = Path.cwd()
    else:
        target_dir = Path(target_dir)
    
    saved = []
    
    # Try specific filenames first: ```filename.ext ... ```
    for match in re.finditer(r'```(\w+\.\w+)\s*\n(.*?)```', content, re.DOTALL):
        filename = match.group(1)
        code = match.group(2).strip()
        if code and len(code) > 10:
            filepath = target_dir / filename
            filepath.write_text(code, encoding='utf-8')
            saved.append({'file': str(filepath), 'name': filename, 'size': len(code)})
    
    # If no named files found, try to detect from content
    if not saved:
        html_match = re.search(r'<!DOCTYPE html>.*?</html>', content, re.DOTALL | re.IGNORECASE)
        if html_match:
            filepath = target_dir / 'index.html'
            filepath.write_text(html_match.group(0), encoding='utf-8')
            saved.append({'file': str(filepath), 'name': 'index.html', 'size': len(html_match.group(0))})
        
        css_match = re.search(r'<style[^>]*>(.*?)</style>', content, re.DOTALL | re.IGNORECASE)
        if css_match and not html_match:
            filepath = target_dir / 'style.css'
            filepath.write_text(css_match.group(1).strip(), encoding='utf-8')
            saved.append({'file': str(filepath), 'name': 'style.css', 'size': len(css_match.group(1))})
        
        js_match = re.search(r'<script[^>]*>(.*?)</script>', content, re.DOTALL | re.IGNORECASE)
        if js_match and not html_match:
            filepath = target_dir / 'script.js'
            filepath.write_text(js_match.group(1).strip(), encoding='utf-8')
            saved.append({'file': str(filepath), 'name': 'script.js', 'size': len(js_match.group(1))})
    
    return saved

def verify_files(saved_files):
    """Verify created files are valid and working."""
    results = []
    for f in saved_files:
        filepath = Path(f['file'])
        name = f['name']
        result = {'file': str(filepath), 'name': name, 'valid': True, 'issues': []}
        
        if name.endswith('.html'):
            content = filepath.read_text(encoding='utf-8')
            # Check basic HTML structure
            if '<html' not in content.lower():
                result['issues'].append('Missing <html> tag')
            if '<body' not in content.lower():
                result['issues'].append('Missing <body> tag')
            if '</html>' not in content.lower():
                result['issues'].append('Missing closing </html> tag')
            if '<!DOCTYPE' not in content:
                result['issues'].append('Missing DOCTYPE declaration')
            
            # Check for common issues
            if content.count('<script') != content.count('</script>'):
                result['issues'].append('Unmatched <script> tags')
            if content.count('<style') != content.count('</style>'):
                result['issues'].append('Unmatched <style> tags')
            
            if result['issues']:
                result['valid'] = False
        
        elif name.endswith('.css'):
            content = filepath.read_text(encoding='utf-8')
            # Check for balanced braces
            if content.count('{') != content.count('}'):
                result['issues'].append('Unbalanced CSS braces')
                result['valid'] = False
        
        elif name.endswith('.js'):
            content = filepath.read_text(encoding='utf-8')
            # Check for basic syntax issues
            if content.count('(') != content.count(')'):
                result['issues'].append('Unbalanced parentheses')
                result['valid'] = False
            if content.count('{') != content.count('}'):
                result['issues'].append('Unbalanced braces')
                result['valid'] = False
        
        results.append(result)
    
    return results

def try_preview_html(filepath):
    """Try to create a preview of the HTML file."""
    try:
        # Read the HTML file
        content = Path(filepath).read_text(encoding='utf-8')
        
        # Create a simple preview by extracting key elements
        title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.DOTALL | re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else 'Preview'
        
        body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
        body = body_match.group(1).strip() if body_match else content
        
        return {
            'title': title,
            'body_preview': body[:500],
            'has_canvas': '<canvas' in content.lower(),
            'has_script': '<script' in content.lower(),
            'has_style': '<style' in content.lower() or '.css' in content.lower(),
        }
    except Exception as e:
        return {'error': str(e)}

HTML = open(Path(__file__).parent / 'widdx-dashboard.html', encoding='utf-8').read()

class WIDDXHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/api/chat':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
            messages = data.get('messages', [])
            api_key = get_api_key()
            if not api_key:
                response = {'error': 'مفتاح API غير موجود'}
            else:
                result = call_deepseek(messages, api_key)
                response = {'content': result}
                
                # Auto-extract and save files if response contains code
                if '```' in result or '<!DOCTYPE' in result or '<html' in result.lower():
                    target_dir = data.get('dir', str(Path.cwd()))
                    saved = extract_and_save_files(result, target_dir)
                    if saved:
                        verification = verify_files(saved)
                        response['files'] = saved
                        response['verification'] = verification
                        response['auto_saved'] = True
                        
                        # Try to preview HTML files
                        for f in saved:
                            if f['name'].endswith('.html'):
                                response['preview'] = try_preview_html(f['file'])
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
        
        elif self.path == '/api/execute':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
            content = data.get('content', '')
            target_dir = data.get('dir', str(Path.cwd()))
            
            saved = extract_and_save_files(content, target_dir)
            verification = verify_files(saved) if saved else []
            
            response = {'files': saved, 'verification': verification}
            
            # Try to preview HTML files
            for f in saved:
                if f['name'].endswith('.html'):
                    response['preview'] = try_preview_html(f['file'])
                    break
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
        
        elif self.path == '/api/verify':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
            files = data.get('files', [])
            verification = verify_files(files)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'verification': verification}).encode('utf-8'))
        
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

def find_free_port(start_port):
    for p in range(start_port, start_port + 20):
        try:
            with socketserver.TCPServer(('localhost', p), WIDDXHandler) as httpd:
                return p
        except OSError:
            continue
    return start_port

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    port = find_free_port(port)
    print(f'WIDDX Nexus running at http://localhost:{port}')
    print(f'Working directory: {Path.cwd()}')
    import webbrowser
    webbrowser.open(f'http://localhost:{port}')
    print('Press Ctrl+C to stop')
    try:
        with socketserver.TCPServer(('localhost', port), WIDDXHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nServer stopped')

def main():
    """Entry point for `widdx-we` command."""
    import webbrowser
    port = find_free_port(8080)
    print(f'WIDDX Nexus running at http://localhost:{port}')
    print(f'Working directory: {Path.cwd()}')
    webbrowser.open(f'http://localhost:{port}')
    print('Press Ctrl+C to stop')
    try:
        with socketserver.TCPServer(('localhost', port), WIDDXHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nServer stopped')
