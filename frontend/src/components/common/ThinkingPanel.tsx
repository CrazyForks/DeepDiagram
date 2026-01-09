import { useState, useEffect } from 'react';
import { ChevronDown, ChevronUp, Brain } from 'lucide-react';
import { cn } from '../../lib/utils';

interface ThinkingPanelProps {
    thought: string;
    isThinking?: boolean;
}

export const ThinkingPanel = ({ thought, isThinking = false }: ThinkingPanelProps) => {
    const [isExpanded, setIsExpanded] = useState(isThinking);

    // Auto-expand when thinking starts, auto-collapse when done
    useEffect(() => {
        if (isThinking) {
            setIsExpanded(true);
        } else {
            // When thinking finishes, collapse after a short delay
            const timer = setTimeout(() => setIsExpanded(false), 500);
            return () => clearTimeout(timer);
        }
    }, [isThinking]);

    if (!thought) return null;

    return (
        <div className={cn(
            "w-full border-b border-slate-200 bg-slate-50 transition-all duration-500",
            isThinking && "border-purple-200 bg-purple-50/30"
        )}>
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full flex items-center justify-between p-3 hover:bg-slate-100 transition-colors"
                title={isExpanded ? "Collapse thinking process" : "Expand thinking process"}
            >
                <div className="flex items-center gap-2 text-slate-600">
                    <Brain className={cn("w-4 h-4", isThinking ? "text-purple-600 animate-pulse" : "text-slate-400")} />
                    <span className="text-xs font-semibold uppercase tracking-wider">
                        {isThinking ? "Thinking..." : "Thinking Process"}
                    </span>
                </div>
                {isExpanded ? (
                    <ChevronUp className="w-4 h-4 text-slate-400" />
                ) : (
                    <ChevronDown className="w-4 h-4 text-slate-400" />
                )}
            </button>
            <div
                className={cn(
                    "overflow-hidden transition-all duration-300 ease-in-out",
                    isExpanded ? "max-h-[500px] opacity-100" : "max-h-0 opacity-0"
                )}
            >
                <div className="p-4 pt-0 text-sm text-slate-600 font-mono whitespace-pre-wrap leading-relaxed border-t border-slate-100/50 shadow-inner">
                    {thought}
                    {isThinking && <span className="inline-block w-2 h-4 ml-1 align-middle bg-purple-500 animate-pulse" />}
                </div>
            </div>
        </div>
    );
};
