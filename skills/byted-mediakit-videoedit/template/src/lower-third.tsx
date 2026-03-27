import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

export type LowerThirdTheme = 'notion' | 'cyberpunk' | 'apple' | 'aurora' | 'douyin';

export type LowerThirdProps = {
  name: string;
  role: string;
  company: string;
  theme?: LowerThirdTheme;
  durationMs?: number;
};

const msToFrames = (ms: number, fps: number) => Math.round((ms / 1000) * fps);

const themeStyles: Record<
  LowerThirdTheme,
  {
    accent: React.CSSProperties;
    name: React.CSSProperties;
    role: React.CSSProperties;
    company: React.CSSProperties;
    content: React.CSSProperties;
  }
> = {
  notion: {
    accent: {
      background: 'linear-gradient(180deg, #DFAB01, #E16259)',
    },
    name: {
      color: '#37352F',
      fontFamily: '"Georgia", "Noto Serif SC", serif',
    },
    role: {
      color: '#787774',
      fontFamily: '-apple-system, "PingFang SC", sans-serif',
    },
    company: {
      color: '#787774',
      fontFamily: '-apple-system, "PingFang SC", sans-serif',
    },
    content: {
      background: 'rgba(255, 253, 247, 0.95)',
      padding: '16px 24px',
      borderRadius: 8,
      boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
    },
  },
  cyberpunk: {
    accent: {
      background: 'linear-gradient(180deg, #00F5FF, #FF00FF)',
      boxShadow: '0 0 20px #00F5FF',
    },
    name: {
      color: '#00F5FF',
      fontFamily: '"Orbitron", sans-serif',
      textShadow: '0 0 10px #00F5FF',
    },
    role: {
      color: '#FF00FF',
      fontFamily: '"Courier New", monospace',
    },
    company: {
      color: '#FF00FF',
      fontFamily: '"Courier New", monospace',
    },
    content: {
      background: 'rgba(13, 13, 13, 0.9)',
      padding: '16px 24px',
      border: '1px solid #00F5FF',
      borderRadius: 4,
    },
  },
  apple: {
    accent: {
      display: 'none',
    },
    name: {
      color: '#1D1D1F',
      fontFamily: '-apple-system, "SF Pro Display", sans-serif',
    },
    role: {
      color: '#86868B',
      fontFamily: '-apple-system, "SF Pro Text", sans-serif',
    },
    company: {
      color: '#86868B',
      fontFamily: '-apple-system, "SF Pro Text", sans-serif',
    },
    content: {
      background: 'rgba(255, 255, 255, 0.8)',
      padding: '16px 24px',
      borderRadius: 12,
      backdropFilter: 'blur(20px)',
    },
  },
  aurora: {
    accent: {
      background: 'linear-gradient(180deg, #667EEA, #764BA2, #F093FB)',
    },
    name: {
      background: 'linear-gradient(135deg, #667EEA, #F093FB)',
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent',
      fontFamily: '"Avenir Next", sans-serif',
    },
    role: {
      color: '#B8B8D0',
      fontFamily: '-apple-system, sans-serif',
    },
    company: {
      color: '#B8B8D0',
      fontFamily: '-apple-system, sans-serif',
    },
    content: {
      background: 'rgba(15, 15, 35, 0.9)',
      padding: '16px 24px',
      borderRadius: 12,
      border: '1px solid rgba(102, 126, 234, 0.3)',
    },
  },
  douyin: {
    accent: {
      background: 'linear-gradient(180deg, #25F4EE, #FE2C55)',
      boxShadow: '0 0 14px rgba(37, 244, 238, 0.5)',
    },
    name: {
      color: '#FFFFFF',
      fontFamily: '"Montserrat", "PingFang SC", sans-serif',
      textShadow: '-2px 0 0 #25F4EE, 2px 0 0 #FE2C55',
    },
    role: {
      color: '#B8B8B8',
      fontFamily: '-apple-system, "PingFang SC", sans-serif',
    },
    company: {
      color: '#B8B8B8',
      fontFamily: '-apple-system, "PingFang SC", sans-serif',
    },
    content: {
      background: 'rgba(11, 11, 11, 0.9)',
      padding: '16px 24px',
      borderRadius: 12,
      border: '1px solid rgba(255, 255, 255, 0.08)',
      boxShadow: '0 8px 20px rgba(0, 0, 0, 0.4)',
    },
  },
};

export const LowerThird: React.FC<LowerThirdProps> = ({
  name,
  role,
  company,
  theme = 'notion',
  durationMs = 5000,
}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const totalFrames = Math.min(durationInFrames, msToFrames(durationMs, fps));
  const enterStart = msToFrames(200, fps);
  const enterEnd = msToFrames(700, fps);
  const titleStart = msToFrames(400, fps);
  const titleEnd = msToFrames(900, fps);
  const exitStart = msToFrames(durationMs - 500, fps);
  const exitEnd = exitStart + msToFrames(400, fps);

  const accentHeight = interpolate(
    frame,
    [0, msToFrames(400, fps), exitStart + msToFrames(200, fps), exitStart + msToFrames(500, fps)],
    [0, 80, 80, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );

  const nameOpacity = interpolate(
    frame,
    [enterStart, enterEnd, exitStart, exitEnd],
    [0, 1, 1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );
  const nameX = interpolate(
    frame,
    [enterStart, enterEnd, exitStart, exitEnd],
    [-20, 0, 0, -20],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );

  const titleOpacity = interpolate(
    frame,
    [titleStart, titleEnd, exitStart, exitEnd],
    [0, 1, 1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );
  const titleX = interpolate(
    frame,
    [titleStart, titleEnd, exitStart, exitEnd],
    [-20, 0, 0, -20],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}
  );

  const themeStyle = themeStyles[theme];

  return (
    <div style={{width: '100%', height: '100%', position: 'relative'}}>
      <div
        style={{
          position: 'absolute',
          bottom: 80,
          left: 60,
          display: 'flex',
          alignItems: 'flex-end',
          gap: 16,
        }}
      >
        <div
          style={{
            width: 4,
            height: accentHeight,
            borderRadius: 2,
            ...themeStyle.accent,
          }}
        />
        <div style={{display: 'flex', flexDirection: 'column', gap: 4, ...themeStyle.content}}>
          <div
            style={{
              fontSize: 36,
              fontWeight: 700,
              opacity: nameOpacity,
              transform: `translateX(${nameX}px)`,
              ...themeStyle.name,
            }}
          >
            {name}
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              opacity: titleOpacity,
              transform: `translateX(${titleX}px)`,
            }}
          >
            <span style={{fontSize: 18, fontWeight: 500, ...themeStyle.role}}>{role}</span>
            <span style={{width: 1, height: 16, background: 'currentColor', opacity: 0.4}} />
            <span style={{fontSize: 18, fontWeight: 400, ...themeStyle.company}}>{company}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
