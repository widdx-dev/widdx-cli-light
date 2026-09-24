/**
 * WIDDX Cortex — VS Code Extension Entry Point
 *
 * Provides:
 *  - Sidebar chat panel with streaming AI responses
 *  - Context menu commands (Explain, Fix, Send to Chat)
 *  - Keyboard shortcuts (Ctrl+Alt+W for chat, Ctrl+Alt+S for selection)
 *  - Status bar indicator showing connection state
 */

import * as vscode from 'vscode';
import { ChatPanelProvider } from './panel';
import { WiddxClient } from './client';
import { randomBytes } from 'crypto';

let client: WiddxClient;
let statusBarItem: vscode.StatusBarItem;
let healthCheckInterval: NodeJS.Timeout | undefined;

export function activate(context: vscode.ExtensionContext) {
    const config = vscode.workspace.getConfiguration('widdx');
    const apiUrl = config.get<string>('apiUrl', 'http://localhost:8000');

    const secretName = `widdx.apiKey:${new URL(apiUrl).origin}`;
    client = new WiddxClient(apiUrl, () => context.secrets.get(secretName));
    context.subscriptions.push(
        vscode.commands.registerCommand('widdx-cortex.setApiKey', async () => {
            const key = await vscode.window.showInputBox({
                title: `WIDDX API key for ${client.baseUrl}`,
                password: true,
                ignoreFocusOut: true,
                prompt: 'Enter the server WIDDX_API_KEY. Stored only in VS Code SecretStorage.',
                validateInput: value => !value.trim() || /\s/.test(value) ? 'Enter a nonempty key without whitespace.' : undefined
            });
            if (key !== undefined) {
                await context.secrets.store(secretName, key);
                await updateHealthStatus();
            }
        })
    );
    console.log('[WIDDX] Extension activated');

    // ── Status Bar ──────────────────────────────────────────
    statusBarItem = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Right,
        100
    );
    statusBarItem.command = 'widdx-cortex.openChat';
    statusBarItem.text = '$(comment-discussion) WIDDX';
    statusBarItem.tooltip = 'Open WIDDX Cortex Chat';
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);

    // ── Chat Panel Provider ─────────────────────────────────
    const chatProvider = new ChatPanelProvider(context.extensionUri, client);
        context.subscriptions.push(
            vscode.window.registerWebviewViewProvider(
                ChatPanelProvider.viewType,
                chatProvider
            )
        );

    // ── Commands ────────────────────────────────────────────

    // Open the chat sidebar
    context.subscriptions.push(
        vscode.commands.registerCommand('widdx-cortex.openChat', () => {
            vscode.commands.executeCommand(
                'workbench.view.extension.widdx-cortex-sidebar'
            );
        })
    );

    // New session
    context.subscriptions.push(
        vscode.commands.registerCommand('widdx-cortex.newSession', async () => {
            await chatProvider.resetSession();
        })
    );

    // Send selection to chat
    context.subscriptions.push(
        vscode.commands.registerCommand('widdx-cortex.sendSelection', () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;

            const selection = editor.document.getText(editor.selection);
            if (!selection) return;

            const message = `Look at this code:\n\`\`\`\n${selection}\n\`\`\``;
            chatProvider.sendMessage(message);
            vscode.commands.executeCommand(
                'workbench.view.extension.widdx-cortex-sidebar'
            );
        })
    );

    // Explain selected code
    context.subscriptions.push(
        vscode.commands.registerCommand('widdx-cortex.explainCode', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;

            const selection = editor.document.getText(editor.selection);
            if (!selection) return;

            const language = editor.document.languageId;
            const message = `Explain this ${language} code in detail:\n\`\`\`${language}\n${selection}\n\`\`\``;
            chatProvider.sendMessage(message);
            vscode.commands.executeCommand(
                'workbench.view.extension.widdx-cortex-sidebar'
            );
        })
    );

    // Fix selected code
    context.subscriptions.push(
        vscode.commands.registerCommand('widdx-cortex.fixCode', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;

            const selection = editor.document.getText(editor.selection);
            if (!selection) return;

            const language = editor.document.languageId;
            const message = `Fix any bugs or issues in this ${language} code:\n\`\`\`${language}\n${selection}\n\`\`\``;
            chatProvider.sendMessage(message);
            vscode.commands.executeCommand(
                'workbench.view.extension.widdx-cortex-sidebar'
            );
        })
    );

    // Review entire file
    context.subscriptions.push(
        vscode.commands.registerCommand('widdx-cortex.reviewFile', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;

            const code = editor.document.getText();
            const language = editor.document.languageId;
            const fileName = editor.document.uri.fsPath.split(/[/\\]/).pop();
            const message = `Review this file (${fileName}) for bugs, security issues, and improvements:\n\`\`\`${language}\n${code}\n\`\`\``;
            chatProvider.sendMessage(message);
            vscode.commands.executeCommand(
                'workbench.view.extension.widdx-cortex-sidebar'
            );
        })
    );

    // Start API server command
    context.subscriptions.push(
        vscode.commands.registerCommand('widdx-cortex.startServer', async () => {
            if (!vscode.workspace.isTrusted) {
                vscode.window.showErrorMessage('Trust this workspace before starting the API server.');
                return;
            }
            const url = new URL(client.baseUrl);
            if (url.protocol !== 'http:' || !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)) {
                vscode.window.showErrorMessage('Start Server supports only local HTTP API URLs. Start remote servers separately.');
                return;
            }
            let key = await context.secrets.get(secretName);
            if (!key) {
                key = randomBytes(32).toString('hex');
                await context.secrets.store(secretName, key);
            }
            const terminal = vscode.window.createTerminal({
                name: 'WIDDX API',
                env: { WIDDX_API_KEY: key, WIDDX_API_HOST: url.hostname === '[::1]' ? '::1' : '127.0.0.1' }
            });
            context.subscriptions.push(terminal);
            terminal.show();
            terminal.sendText(`widdx-api --port ${url.port || '80'}`);
            vscode.window.showInformationMessage(
                'Starting WIDDX API server... Check the terminal for output.'
            );
        })
    );

    // ── Health Check Polling ────────────────────────────────
    async function updateHealthStatus() {
        try {
            const healthy = await client.healthCheck();
            if (healthy) {
                statusBarItem.text = '$(check) WIDDX';
                statusBarItem.tooltip = 'WIDDX Cortex — Connected';
            } else {
                statusBarItem.text = '$(warning) WIDDX';
                statusBarItem.tooltip = 'WIDDX Cortex — Server unreachable';
            }
        } catch {
            statusBarItem.text = '$(circle-slash) WIDDX';
            statusBarItem.tooltip = 'WIDDX Cortex — Disconnected';
        }
    }

    updateHealthStatus();
    healthCheckInterval = setInterval(updateHealthStatus, 30000);
    context.subscriptions.push({
        dispose: () => {
            if (healthCheckInterval) clearInterval(healthCheckInterval);
        }
    });

    // ── Editor change listener for context updates ──────────
    context.subscriptions.push(
        vscode.window.onDidChangeActiveTextEditor(() => {
            // The chat panel handles context internally
        })
    );

    console.log('[WIDDX] Extension ready');
}

export function deactivate() {
    if (healthCheckInterval) {
        clearInterval(healthCheckInterval);
    }
    console.log('[WIDDX] Extension deactivated');
}
