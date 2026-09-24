export interface ProviderInfo {
    current: string;
    model: string;
    available: string[];
    models: unknown[];
}

export interface SessionInfo {
    session_id: 'shared';
    messages: number;
    turns: number;
}

export interface ChatContext {
    filePath?: string;
    fileContent?: string;
    selection?: string;
}

export interface ChatResponse {
    response: string;
    model: string;
    turns: number;
    cost: number;
    session_id: 'shared';
}

export class WiddxClient {
    public readonly baseUrl: string;

    constructor(baseUrl: string, private readonly getApiKey: () => PromiseLike<string | undefined>) {
        const url = new URL(baseUrl);
        const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
        if ((url.protocol !== 'https:' && !(url.protocol === 'http:' && local)) ||
            url.username || url.password || url.search || url.hash || url.pathname !== '/') {
            throw new Error('Use an HTTPS API origin, or HTTP on localhost, without credentials or a path.');
        }
        this.baseUrl = url.origin;
    }

    private async request(path: string, method = 'GET', body?: unknown): Promise<unknown> {
        const key = await this.getApiKey();
        if (!key) throw new Error('Set the API key using WIDDX Cortex: Set API Key.');
        let res;
        try {
            res = await fetch(`${this.baseUrl}${path}`, {
                method,
                headers: { 'Authorization': `Bearer ${key}`, 'Content-Type': 'application/json' },
                body: body === undefined ? undefined : JSON.stringify(body),
                redirect: 'error',
                signal: AbortSignal.timeout(path === '/api/chat' ? 600000 : 10000)
            });
        } catch {
            throw new Error('WIDDX API request failed or timed out. Check the server; a submitted turn may still complete.');
        }
        if (res.status === 401 || res.status === 503) {
            throw new Error('API authentication failed. Set an API key matching the server WIDDX_API_KEY.');
        }
        if (!res.ok) throw new Error(`WIDDX API returned HTTP ${res.status}.`);
        return res.json();
    }

    async healthCheck(): Promise<boolean> {
        try {
            await this.listSessions();
            return true;
        } catch {
            return false;
        }
    }

    async getProviders(): Promise<ProviderInfo> {
        return await this.request('/api/providers') as ProviderInfo;
    }

    async getTools(): Promise<string[]> {
        const data = await this.request('/api/tools') as { base: { name: string }[]; mcp: { name: string }[] };
        return [...data.base, ...data.mcp].map(tool => tool.name);
    }

    async listSessions(): Promise<SessionInfo> {
        return await this.request('/api/sessions') as SessionInfo;
    }

    async clearSession(): Promise<void> {
        await this.request('/api/sessions', 'DELETE');
    }

    async sendMessage(message: string, context?: ChatContext): Promise<ChatResponse> {
        const data = await this.request('/api/chat', 'POST', {
            message,
            stream: false,
            session_id: 'shared',
            context: context ? {
                file_path: context.filePath,
                file_content: context.fileContent,
                selection: context.selection
            } : undefined
        }) as ChatResponse;
        if (data.session_id !== 'shared' || typeof data.response !== 'string') {
            throw new Error('Unexpected API chat response. Check the server version.');
        }
        return data;
    }
}
