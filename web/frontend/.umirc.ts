import { defineConfig } from '@umijs/max';

export default defineConfig({
  antd: {},
  esbuildMinifyIIFE: true,
  layout: false,
  routes: [
      { path: '/', redirect: '/dashboard' },
      { path: '/dashboard', component: '@/pages/dashboard' },
      { path: '/ai-detection', component: '@/pages/ai-detection' },
      { path: '/ai-inference', component: '@/pages/ai-detection' },
      { path: '/experiments', component: '@/pages/experiments' },
      { path: '/generalization', component: '@/pages/generalization' },
      { path: '/gallery', component: '@/pages/gallery' },
      { path: '/presentation-demo', component: '@/pages/presentation-demo' },
      { path: '/interactive-lab', component: '@/pages/interactive-lab' },
      { path: '/interactive-lab/heartbeat-hunter', component: '@/pages/interactive-lab/HeartbeatHunter' },
  ],
  proxy: {
    '/api': {
      target: process.env.ECG_API_PROXY || 'http://127.0.0.1:8000',
      changeOrigin: true,
    },
  },
  npmClient: 'npm',
  title: 'ECG-AI · MIT-BIH 教学工作台',
  favicons: ['/ecg-mark.svg'],
  history: { type: 'browser' },
});
