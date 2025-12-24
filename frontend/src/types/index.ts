export type AgentType = 'mindmap' | 'flowchart' | 'charts' | 'drawio' | 'mermaid' | 'general';

export interface Step {
    type: 'agent_select' | 'tool_start' | 'tool_end';
    name?: string; // e.g. "mindmap_agent", "create_chart"
    content?: string; // Input or Output
    status?: 'running' | 'done' | 'error';
    timestamp?: number;
    error?: string;
    isError?: boolean;
    isStreaming?: boolean;
}

export interface Message {
    id?: number;
    parent_id?: number | null;
    role: 'user' | 'assistant' | 'system';
    content: string;
    images?: string[];
    steps?: Step[]; // Execution trace
    agent?: AgentType | string;
    created_at?: string;
}

export interface ChatSession {
    id: number;
    title: string;
    created_at: string;
    updated_at: string;
}

export interface ChartOption {
    // Loose typing for ECharts option
    [key: string]: any;
}

export interface ChatState {
    messages: Message[];
    input: string;
    activeAgent: AgentType;
    currentCode: string; // The code currently rendered (markdown, mermaid, or echarts json)
    isLoading: boolean;
    sessionId: number | null;
    sessions: ChatSession[];
    allMessages: Message[];
    inputImages: string[]; // Base64 data URLs
    isStreamingCode: boolean;
    selectedVersions: Record<number, number>; // parentId -> selected messageId

    setInput: (input: string) => void;
    setAgent: (agent: AgentType) => void;
    addMessage: (message: Message) => void;
    setCurrentCode: (code: string | ((prev: string) => string)) => void;
    setLoading: (loading: boolean) => void;
    setStreamingCode: (streaming: boolean) => void;
    setSessionId: (id: number | null) => void;
    setMessages: (messages: Message[]) => void;
    updateLastMessage: (content: string) => void;
    setInputImages: (images: string[]) => void;
    addInputImage: (image: string) => void;
    clearInputImages: () => void;
    addStepToLastMessage: (step: import('../types').Step) => void;
    markLastStepAsError: (error: string) => void;
    activeStepRef: { messageIndex: number; stepIndex: number } | null;
    setActiveStepRef: (ref: { messageIndex: number; stepIndex: number } | null) => void;
    reportError: (error: string) => void;
    reportSuccess: () => void;
    toast: { message: string; type: 'error' | 'success' } | null;
    updateLastStepContent: (content: string, isStreaming?: boolean, status?: 'running' | 'done') => void;
    clearToast: () => void;

    // Session management
    loadSessions: () => Promise<void>;
    selectSession: (sessionId: number) => Promise<void>;
    createNewChat: () => void;
    deleteSession: (sessionId: number) => Promise<void>;
    switchMessageVersion: (messageId: number) => void;
}
