import React from 'react';
import { ConfigProvider, App as AntApp } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { AnimationProvider, useMotionSettings } from '@/utils/motion';
import './styles/motion.less';

function MotionAntProvider({children}:{children:React.ReactNode}) {
  const {reduced}=useMotionSettings();
  return <ConfigProvider theme={{token:{motion:!reduced}}}>{children}</ConfigProvider>;
}

export function rootContainer(container: React.ReactNode) {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#1677FF',
          colorInfo: '#1677FF',
          colorSuccess: '#16A34A',
          colorWarning: '#B7790A',
          colorError: '#DC2626',
          borderRadius: 8,
          fontFamily: '"Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif',
          colorText: '#182B49',
          colorTextSecondary: '#64748B',
          colorBgLayout: '#F7FAFF',
          colorBorderSecondary: '#E4ECF5',
          fontSize: 14,
          controlHeight: 36,
        },
      }}
    >
      <AnimationProvider><MotionAntProvider><AntApp>{container}</AntApp></MotionAntProvider></AnimationProvider>
    </ConfigProvider>
  );
}
