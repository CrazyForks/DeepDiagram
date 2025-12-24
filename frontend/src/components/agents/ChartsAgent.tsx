import { useEffect, useRef, useImperativeHandle, forwardRef, useState } from 'react';
import { useChatStore } from '../../store/chatStore';
import * as echarts from 'echarts';
import type { AgentRef } from './types';
import { AlertCircle } from 'lucide-react';

export const ChartsAgent = forwardRef<AgentRef>((_, ref) => {
    const { currentCode, isStreamingCode } = useChatStore();
    const chartRef = useRef<HTMLDivElement>(null);
    const chartInstanceRef = useRef<echarts.ECharts | null>(null);
    const [error, setError] = useState<string | null>(null);

    useImperativeHandle(ref, () => ({
        handleDownload: async (type: 'png' | 'svg') => {
            if (!chartInstanceRef.current) return;
            const filename = `deepdiagram-charts-${new Date().getTime()}`;

            const downloadFile = (url: string, ext: string) => {
                const a = document.createElement('a');
                a.href = url;
                a.download = `${filename}.${ext}`;
                a.click();
            };

            if (type === 'png') {
                const url = chartInstanceRef.current.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#fff' });
                downloadFile(url, 'png');
            } else {
                alert('SVG export for charts is not currently supported in this mode.');
            }
        }
    }));

    useEffect(() => {
        if (!currentCode || !chartRef.current) {
            if (chartInstanceRef.current) {
                chartInstanceRef.current.dispose();
                chartInstanceRef.current = null;
            }
            return;
        }
        if (isStreamingCode) return;

        const chart = echarts.init(chartRef.current);
        chartInstanceRef.current = chart;

        try {
            setError(null);

            // Robustly strip markdown blocks if they exist
            let cleanCode = currentCode.trim();
            const match = cleanCode.match(/```(?:json|chart)?\s*([\s\S]*?)\s*```/i);
            if (match) {
                cleanCode = match[1].trim();
            }

            let options: any;
            try {
                // Try standard JSON first
                options = JSON.parse(cleanCode);
            } catch {
                // Fallback to Function constructor to support functions/comments in the config
                options = new Function(`return (${cleanCode})`)();
            }

            const hasAxis = options.xAxis || options.yAxis || (options.grid && !options.series?.some((s: any) => s.type === 'pie'));

            if (hasAxis) {
                if (!options.dataZoom) {
                    options.dataZoom = [
                        { type: 'inside', xAxisIndex: [0], filterMode: 'filter' },
                        { type: 'slider', xAxisIndex: [0], filterMode: 'filter' }
                    ];
                }
                if (!options.tooltip) options.tooltip = { trigger: 'axis', confine: true };
            }

            if (options.series) {
                options.series = options.series.map((s: any) => {
                    if (['graph', 'tree', 'map', 'sankey'].includes(s.type)) {
                        return { ...s, roam: true };
                    }
                    return s;
                });
            }

            chart.setOption(options);

            // Report success to clear any potential previous error
            useChatStore.getState().reportSuccess();

            const resizeObserver = new ResizeObserver(() => chart.resize());
            resizeObserver.observe(chartRef.current);

            return () => {
                resizeObserver.disconnect();
                chart.dispose();
            };
        } catch (e) {
            console.error("ECharts error", e);
            const msg = e instanceof Error ? e.message : "Failed to render chart";
            setError(msg);
            useChatStore.getState().reportError(msg);
        }
    }, [currentCode, isStreamingCode]);

    return (
        <div className="w-full h-full relative bg-white">
            {error ? (
                <div className="flex flex-col items-center justify-center h-full p-4 text-center">
                    <div className="p-3 bg-red-50 rounded-full mb-3">
                        <AlertCircle className="w-6 h-6 text-red-500" />
                    </div>
                    <p className="text-sm font-semibold text-slate-800">Chart Render Failed</p>
                    <p className="text-xs text-slate-500 mt-1 mb-4 max-w-xs">{error}</p>
                    <button
                        onClick={() => window.dispatchEvent(new CustomEvent('deepdiagram-retry', {
                            detail: { index: useChatStore.getState().messages.length - 1 }
                        }))}
                        className="px-4 py-2 bg-slate-900 text-white rounded-lg text-xs font-bold hover:bg-slate-800 transition-colors"
                    >
                        Try Regenerating
                    </button>
                </div>
            ) : (
                <div ref={chartRef} className="w-full h-full" />
            )}
        </div>
    );
});
