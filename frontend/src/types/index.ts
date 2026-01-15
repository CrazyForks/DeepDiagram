export type AgentType = 'mindmap' | 'flowchart' | 'charts' | 'drawio' | 'mermaid' | 'infographic' | 'general';

export interface Step {
    type: 'agent_select' | 'tool_start' | 'tool_end' | 'doc_analysis' | 'agent_end';
    name?: string; // e.g. "mindmap_agent", "create_chart"
    content?: string; // Input or Output
    status: 'running' | 'done' | 'error';
    timestamp: number;
    isStreaming?: boolean;
    isError?: boolean;
}

export interface DocAnalysisBlock {
    index: number;
    content: string;
    thinking?: string;
    status: 'running' | 'done';
}

export interface FileData {
    name: string;
    data: string;
}

export interface VersionInfo {
    current: number;
    total: number;
}

export interface Message {
    id?: number;
    parent_id?: number | null;
    role: 'user' | 'assistant' | 'system';
    content: string;
    images?: string[];
    files?: { name: string, data: string }[];
    steps?: Step[]; // Execution trace
    agent?: AgentType | string;
    turn_index?: number;
    created_at?: string;
    error?: string; // Optional error message
    docAnalysisBlocks?: DocAnalysisBlock[];
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
    isLoading: boolean;
    sessionId: number | null;
    sessions: ChatSession[];
    allMessages: Message[];
    inputImages: string[]; // Base64 data URLs
    isStreamingCode: boolean;
    activeMessageId: number | null;
    selectedVersions: Record<number, number>; // turnIndex -> selected messageId
    inputFiles: { name: string, data: string }[];
    parsingStatus: string | null;

    setInput: (input: string) => void;
    setAgent: (agent: AgentType) => void;
    addMessage: (message: Message) => void;
    setLoading: (loading: boolean) => void;
    setStreamingCode: (streaming: boolean) => void;
    setSessionId: (id: number | null) => void;
    setMessages: (messages: Message[]) => void;
    updateLastMessage: (content: string, isStreaming?: boolean, status?: 'running' | 'done' | 'error', sessionId?: number, skipCanvasSync?: boolean) => void;
    setActiveMessageId: (id: number | null) => void;
    addStepToLastMessage: (step: Step, sessionId?: number) => void;
    updateLastStepContent: (content: string, isStreaming?: boolean, status?: 'running' | 'done', type?: Step['type'], append?: boolean, sessionId?: number) => void;
    updateDocAnalysisBlock: (index: number, content: string, status: 'running' | 'done', append?: boolean, sessionId?: number) => void;
    replaceLastStep: (step: Step, sessionId?: number) => void;
    activeStepRef: { messageIndex: number, stepIndex: number } | null;
    setActiveStepRef: (ref: { messageIndex: number, stepIndex: number } | null) => void;

    setInputImages: (images: string[]) => void;
    addInputImage: (image: string) => void;
    clearInputImages: () => void;
    setInputFiles: (files: { name: string, data: string }[]) => void;
    addInputFile: (file: { name: string, data: string }) => void;
    clearInputFiles: () => void;
    setParsingStatus: (status: string | null) => void;

    reportError: (error: string) => void;
    reportSuccess: () => void;
    toast: { message: string; type: 'error' | 'success' } | null;
    clearToast: () => void;

    // Session management
    loadSessions: () => Promise<void>;
    selectSession: (sessionId: number) => Promise<void>;
    createNewChat: () => void;
    deleteSession: (sessionId: number) => Promise<void>;
    switchMessageVersion: (messageId: number) => void;
    syncCodeToMessage: (messageId: number) => void;
    handleSync: (msg: Message) => void;
    syncToLatest: () => void;
}
