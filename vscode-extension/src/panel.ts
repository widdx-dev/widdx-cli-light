/**
 * WIDDX Cortex Chat Panel — webview-based sidebar chat interface.
 */

import * as vscode from 'vscode';
import { WiddxClient, ChatContext } from './client';

export class ChatPanelProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'widdx-cortex.chatView';
    private _view?: vscode.WebviewView;
    private client: WiddxClient;
    private busy = false;

    constructor(
        private readonly _extensionUri: vscode.Uri,
        client: WiddxClient
    ) {
        this.client = client;
    }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        _context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [
                vscode.Uri.joinPath(this._extensionUri, 'media'),
                vscode.Uri.joinPath(this._extensionUri, 'out')
            ]
        };

        webviewView.webview.html = this._getHtml(webviewView.webview);

        webviewView.webview.onDidReceiveMessage(async (message) => {
            switch (message.type) {
                case 'sendMessage':
                    await this._handleUserMessage(message.text);
                    break;
                case 'newSession':
                    await this._handleNewSession();
                    break;
                case 'clearChat':
                    await this._handleNewSession();
                    break;
                case 'getContext':
                    await this._sendContext();
                    break;
            }
        });

        this._sendContext();
    }

    private _postMessage(message: unknown) {
        this._view?.webview.postMessage(message);
    }

    private async _handleUserMessage(text: string) {
        if (this.busy) {
            this._postMessage({ type: 'systemMessage', text: 'Wait for the current response before sending another message.' });
            return;
        }
        this.busy = true;
        this._postMessage({ type: 'busy', text: 'Thinking...' });
        this._postMessage({ type: 'userMessage', text });

        const editor = vscode.window.activeTextEditor;
        const context: ChatContext = {};
        if (editor) {
            context.filePath = editor.document.uri.fsPath;
            context.fileContent = editor.document.getText();
            context.selection = editor.document.getText(editor.selection);
        }

        try {
            const reply = await this.client.sendMessage(text, context);
            this._postMessage({ type: 'content', text: reply.response });
            this._postMessage({ type: 'done', text: `${reply.model} · turns ${reply.turns}` });
        } catch (error) {
            this._postMessage({
                type: 'error',
                text: error instanceof Error ? error.message : 'WIDDX API request failed.'
            });
        } finally {
            this.busy = false;
        }
    }

    public async resetSession(): Promise<void> {
        if (this.busy) {
            this._postMessage({ type: 'systemMessage', text: 'Wait for the current turn before starting a new session.' });
            return;
        }
        try {
            await this.client.clearSession();
        } catch (error) {
            this._postMessage({
                type: 'error',
                text: error instanceof Error ? error.message : 'Failed to clear the session.'
            });
            return;
        }
        this._postMessage({ type: 'systemMessage', text: 'New session started.' });
        this._postMessage({ type: 'clearChat' });
    }

    private async _handleNewSession() {
        await this.resetSession();
    }

    private async _sendContext() {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            const selection = editor.selection;
            const file = editor.document;
            this._postMessage({
                type: 'contextUpdate',
                context: {
                    file: file.uri.fsPath.split(/[/\\]/).pop(),
                    language: file.languageId,
                    lines: file.lineCount,
                    hasSelection: !selection.isEmpty,
                    selectedLines: selection.isEmpty ? 0 : selection.end.line - selection.start.line + 1
                }
            });
        }
    }

    public sendMessage(text: string) {
        if (this.busy) {
            this._postMessage({ type: 'systemMessage', text: 'Wait for the current turn before sending another message.' });
            return;
        }
        this._handleUserMessage(text);
    }

    private _getHtml(webview: vscode.Webview): string {
        const styleUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, 'media', 'style.css')
        );

        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="${styleUri}">
    <title>WIDDX Cortex Chat</title>
</head>
<body>
    <div id="chat-container">
        <div id="chat-header">
            <span class="brand">🧠 WIDDX Cortex</span>
            <div class="header-actions">
                <button id="btn-new-session" title="New Session">+</button>
                <button id="btn-clear" title="Clear Chat">🗑</button>
            </div>
        </div>

        <div id="context-bar">
            <span id="ctx-file">No file open</span>
            <span id="ctx-model">Loading...</span>
        </div>

        <div id="messages"></div>

        <div id="input-area">
            <textarea id="chat-input" rows="2"
                placeholder="Ask WIDDX about your code... (Shift+Enter for new line)"
            ></textarea>
            <button id="btn-send">Send</button>
        </div>

        <div id="status-bar">
            <span id="status-text">⚪ Disconnected</span>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        const messagesEl = document.getElementById('messages');
        const inputEl = document.getElementById('chat-input');
        const sendBtn = document.getElementById('btn-send');
        const statusEl = document.getElementById('status-text');
        const ctxFileEl = document.getElementById('ctx-file');
        let currentAiMsg = null;

        function sendMessage() {
            const text = inputEl.value.trim();
            if (!text || sendBtn.disabled) return;
            inputEl.value = '';
            vscode.postMessage({ type: 'sendMessage', text });
            sendBtn.disabled = true;
        }

        sendBtn.addEventListener('click', sendMessage);
        inputEl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        document.getElementById('btn-new-session').addEventListener('click', () => {
            vscode.postMessage({ type: 'newSession' });
        });

        document.getElementById('btn-clear').addEventListener('click', () => {
            vscode.postMessage({ type: 'clearChat' });
        });

        window.addEventListener('message', (event) => {
            const msg = event.data;
            switch (msg.type) {
                case 'userMessage':
                    addMessage('user', msg.text);
                    break;

                case 'busy':
                    showThinking(true);
                    break;

                case 'content':
                    showThinking(false);
                    appendToAi(msg.text);
                    break;

                case 'done':
                    showThinking(false);
                    currentAiMsg = null;
                    sendBtn.disabled = false;
                    if (msg.text) addMessage('meta', msg.text);
                    setStatus('🟢 Connected', 'connected');
                    break;

                case 'error':
                    showThinking(false);
                    addMessage('error', '❌ ' + msg.text);
                    currentAiMsg = null;
                    sendBtn.disabled = false;
                    setStatus('🔴 Error', 'error');
                    break;

                case 'systemMessage':
                    addMessage('system', '⚙ ' + msg.text);
                    break;

                case 'clearChat':
                    messagesEl.innerHTML = '';
                    currentAiMsg = null;
                    break;

                case 'contextUpdate':
                    if (msg.context) {
                        const c = msg.context;
                        ctxFileEl.textContent = c.file
                            ? c.language.toUpperCase() + ' ' + c.file + ' (' + c.lines + ' lines)'
                            : 'No file open';
                    }
                    break;
            }
        });

        function addMessage(type, text) {
            const div = document.createElement('div');
            div.className = 'message msg-' + type;
            div.textContent = text;
            messagesEl.appendChild(div);
            scrollToBottom();
        }

        function appendToAi(text) {
            if (!currentAiMsg) {
                currentAiMsg = document.createElement('div');
                currentAiMsg.className = 'message msg-ai';
                messagesEl.appendChild(currentAiMsg);
            }
            currentAiMsg.textContent += text;
            scrollToBottom();
        }

        function showThinking(show) {
            let el = document.getElementById('thinking-indicator');
            if (show) {
                if (!el) {
                    el = document.createElement('div');
                    el.id = 'thinking-indicator';
                    el.className = 'message msg-thinking';
                    el.textContent = '🤔 Thinking...';
                    messagesEl.appendChild(el);
                }
            } else {
                if (el) el.remove();
            }
        }

        function setStatus(text, cls) {
            statusEl.textContent = text;
            statusEl.className = cls || '';
        }

        function scrollToBottom() {
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }

        function checkConnection() {
            setStatus('🟡 Connecting...', 'connecting');
            vscode.postMessage({ type: 'getContext' });
        }
        checkConnection();
    </script>
</body>
</html>`;
    }
}
