export const CLASS_COLORS: Record<string, string> = { N: '#1677FF', S: '#9254DE', V: '#E64980', F: '#089DB6', Q: '#64748B', other: '#64748B' };
export const TASK_LABELS = { nv: ['N', 'V'], nsvf: ['N', 'S', 'V', 'F'] };
export const pct = (value: string | number) => `${(Number(value) * 100).toFixed(2)}%`;
