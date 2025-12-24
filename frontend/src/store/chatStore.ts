import { create } from 'zustand';
import type { ChatState, Message, AgentType } from '../types';

export const useChatStore = create<ChatState>((set) => ({
    messages: [],
    input: '',
    activeAgent: 'mindmap',
    currentCode: '',
    isLoading: false,
    sessionId: null,
    sessions: [],
    allMessages: [],
    inputImages: [],
    isStreamingCode: false,
    selectedVersions: {},
    toast: null, // Simple toast state
    activeStepRef: null,

    setInput: (input) => set({ input }),
    setAgent: (agent) => set({ activeAgent: agent }),
    addMessage: (message) => set((state) => {
        const newMessage = { ...message, created_at: message.created_at || new Date().toISOString() };
        return {
            messages: [...state.messages, newMessage],
            allMessages: [...state.allMessages, newMessage]
        };
    }),
    setCurrentCode: (code: string | ((prev: string) => string)) =>
        set((state) => ({
            currentCode: typeof code === 'function' ? code(state.currentCode) : code
        })),
    setLoading: (loading) => set({ isLoading: loading }),
    setStreamingCode: (streaming) => set({ isStreamingCode: streaming }),
    setSessionId: (id) => set({ sessionId: id }),
    setMessages: (messages: Message[]) => set({ messages }),
    updateLastMessage: (content) => set((state) => {
        const msgs = [...state.messages];
        if (msgs.length > 0 && msgs[msgs.length - 1].role === 'assistant') {
            msgs[msgs.length - 1].content = content;
        } else {
            // Should probably add if not exists, but usually we add 'assistant' empty msg first
        }
        return { messages: msgs };
    }),
    setInputImages: (images) => set({ inputImages: images }),
    addInputImage: (image) => set((state) => ({ inputImages: [...state.inputImages, image] })),
    clearInputImages: () => set({ inputImages: [] }),
    addStepToLastMessage: (step) => set((state) => {
        const msgs = [...state.messages];
        if (msgs.length > 0) {
            const lastMsg = msgs[msgs.length - 1];
            if (lastMsg.role === 'assistant') {
                lastMsg.steps = lastMsg.steps || [];
                lastMsg.steps.push(step);
            }
        }
        return { messages: msgs };
    }),
    updateLastStepContent: (content: string, isStreaming?: boolean, status?: 'running' | 'done') => set((state) => {
        const msgs = [...state.messages];
        if (msgs.length > 0) {
            const lastMsg = msgs[msgs.length - 1];
            if (lastMsg.role === 'assistant' && lastMsg.steps && lastMsg.steps.length > 0) {
                const lastStep = lastMsg.steps[lastMsg.steps.length - 1];
                if (typeof content === 'string') {
                    lastStep.content = (lastStep.content || '') + content;
                }
                if (isStreaming !== undefined) lastStep.isStreaming = isStreaming;
                if (status !== undefined) lastStep.status = status;
            }
        }
        return { messages: msgs };
    }),


    setActiveStepRef: (ref) => set({ activeStepRef: ref }),

    reportError: (errorMsg) => set((state) => {
        const msgs = [...state.messages];
        let targetStep = null;

        if (state.activeStepRef) {
            const { messageIndex, stepIndex } = state.activeStepRef;
            if (msgs[messageIndex] && msgs[messageIndex].steps && msgs[messageIndex].steps![stepIndex]) {
                targetStep = msgs[messageIndex].steps![stepIndex];
            }
        } else if (msgs.length > 0) {
            // Fallback to last step of last message
            const lastMsg = msgs[msgs.length - 1];
            if (lastMsg.steps && lastMsg.steps.length > 0) {
                targetStep = lastMsg.steps[lastMsg.steps.length - 1];
            }
        }

        if (targetStep) {
            targetStep.isError = true;
            targetStep.error = errorMsg;
            // Force re-render of components using messages
            return { messages: msgs, toast: { message: errorMsg, type: 'error' } };
        }

        return { toast: { message: errorMsg, type: 'error' } };
    }),

    reportSuccess: () => set((state) => {
        if (!state.activeStepRef) return {}; // Do nothing if not explicit re-render? Or clear last?

        const msgs = [...state.messages];
        const { messageIndex, stepIndex } = state.activeStepRef;

        if (msgs[messageIndex] && msgs[messageIndex].steps && msgs[messageIndex].steps![stepIndex]) {
            const targetStep = msgs[messageIndex].steps![stepIndex];
            targetStep.isError = false;
            targetStep.error = undefined;
            return { messages: msgs };
        }
        return {};
    }),

    markLastStepAsError: (errorMsg) => useChatStore.getState().reportError(errorMsg),

    clearToast: () => set({ toast: null }),

    loadSessions: async () => {
        try {
            const response = await fetch('/api/sessions');
            if (response.ok) {
                const sessions = await response.json();
                set({ sessions });
            }
        } catch (error) {
            console.error('Failed to load sessions:', error);
        }
    },

    selectSession: async (sessionId: number) => {
        set({ isLoading: true, sessionId, messages: [], allMessages: [], selectedVersions: {} });
        try {
            const response = await fetch(`/api/sessions/${sessionId}`);
            if (response.ok) {
                const history = await response.json();
                const mappedMessages: Message[] = history.map((msg: any) => ({
                    id: msg.id,
                    parent_id: msg.parent_id,
                    role: msg.role,
                    content: msg.content,
                    images: msg.images || [],
                    steps: msg.steps || [],
                    agent: msg.agent,
                    created_at: msg.created_at
                }));

                // Reconstruct the active branch (default to latest path) and populate selectedVersions
                let activeMessages: Message[] = [];
                const initialSelected: Record<number, number> = {};
                if (mappedMessages.length > 0) {
                    // Start from the most recent message and trace back
                    let current = mappedMessages[mappedMessages.length - 1];
                    const branch: Message[] = [];
                    while (current) {
                        branch.push(current);
                        if (current.parent_id !== null && current.parent_id !== undefined) {
                            initialSelected[current.parent_id] = current.id!;
                        }
                        const parentId = current.parent_id;
                        current = mappedMessages.find(m => m.id === parentId) as Message;
                    }
                    activeMessages = branch.reverse();
                }

                // Restore currentCode and activeAgent from the last assistant message's code output
                let lastCode = '';
                let lastAgent: AgentType = 'mindmap'; // Default fallback
                for (let i = activeMessages.length - 1; i >= 0; i--) {
                    const msg = activeMessages[i];
                    if (msg.role === 'assistant' && msg.steps) {
                        const lastStep = [...msg.steps].reverse().find((s: any) => s.type === 'tool_end' && s.content);
                        if (lastStep && lastStep.content) {
                            lastCode = lastStep.content;
                            if (msg.agent) {
                                lastAgent = msg.agent as AgentType;
                            }
                            break;
                        }
                    }
                }

                set({
                    messages: activeMessages,
                    allMessages: mappedMessages,
                    selectedVersions: initialSelected,
                    currentCode: lastCode,
                    activeAgent: lastAgent,
                    isLoading: false
                });
            }
        } catch (error) {
            console.error('Failed to load session history:', error);
            set({ isLoading: false });
        }
    },

    switchMessageVersion: (messageId: number) => {
        set((state) => {
            const allMsgs = state.allMessages;
            const targetMsg = allMsgs.find(m => m.id === messageId);
            if (!targetMsg) return {};

            // 1. Build path from root to targetMsg
            const branchToTarget: Message[] = [];
            let current: Message | undefined = targetMsg;
            while (current) {
                branchToTarget.push(current);
                const pid: number | null | undefined = current.parent_id;
                current = allMsgs.find(m => m.id === pid);
            }
            branchToTarget.reverse();

            // 2. Follow descendants using selectedVersions or fallback to latest
            const fullPath = [...branchToTarget];
            const newSelectedVersions = { ...state.selectedVersions };

            // Record selection for the target message's parent level
            if (targetMsg.parent_id !== undefined && targetMsg.parent_id !== null) {
                newSelectedVersions[targetMsg.parent_id] = targetMsg.id!;
            }

            let leafCurrent = targetMsg;
            while (true) {
                const children = allMsgs.filter(m => m.parent_id === leafCurrent.id);
                if (children.length === 0) break;

                // Use previously selected version if available, else latest
                const selectedId = newSelectedVersions[leafCurrent.id!];
                leafCurrent = children.find(c => c.id === selectedId) || children[children.length - 1];

                newSelectedVersions[leafCurrent.parent_id!] = leafCurrent.id!;
                fullPath.push(leafCurrent);
            }

            // 3. Update currentCode and agent
            let lastCode = '';
            let lastAgent: AgentType = state.activeAgent;
            for (let i = fullPath.length - 1; i >= 0; i--) {
                const msg = fullPath[i];
                if (msg.role === 'assistant' && msg.steps) {
                    const lastStep = [...msg.steps].reverse().find((s: any) => s.type === 'tool_end' && s.content);
                    if (lastStep && lastStep.content) {
                        lastCode = lastStep.content;
                        if (msg.agent) lastAgent = msg.agent as AgentType;
                        break;
                    }
                }
            }

            return {
                messages: fullPath,
                currentCode: lastCode,
                activeAgent: lastAgent,
                selectedVersions: newSelectedVersions
            };
        });
    },

    createNewChat: () => {
        set({
            messages: [],
            allMessages: [],
            selectedVersions: {},
            sessionId: null,
            currentCode: '',
            input: '',
            inputImages: []
        });
    },

    deleteSession: async (sessionId: number) => {
        try {
            const response = await fetch(`/api/sessions/${sessionId}`, {
                method: 'DELETE'
            });
            if (response.ok) {
                set((state) => ({
                    sessions: state.sessions.filter(s => s.id !== sessionId),
                    sessionId: state.sessionId === sessionId ? null : state.sessionId,
                    messages: state.sessionId === sessionId ? [] : state.messages
                }));
            }
        } catch (error) {
            console.error('Failed to delete session:', error);
        }
    }
}));
