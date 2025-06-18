import React, { useEffect, useRef, useCallback, Component, ErrorInfo } from 'react';
import { Terminal } from 'xterm';
import { WebglAddon } from 'xterm-addon-webgl';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';

const TOKEN_KEY = 'auth_token';

class ErrorBoundary extends Component<{ children: React.ReactNode }, { hasError: boolean }> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Terminal Error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '1rem', color: '#ff0000' }}>
          Terminal error occurred. Please try refreshing the page.
        </div>
      );
    }
    return this.props.children;
  }
}

interface SSHTerminalProps {
  vmId: number;
  apiBaseUrl: string;
}

const TerminalComponent: React.FC<SSHTerminalProps> = ({ vmId, apiBaseUrl }) => {
  const terminalRef = useRef<HTMLDivElement>(null);
  const websocketRef = useRef<WebSocket | null>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const webglAddonRef = useRef<WebglAddon | null>(null);

  const handleResize = useCallback(() => {
    if (fitAddonRef.current) {
      try {
        fitAddonRef.current.fit();
        const term = xtermRef.current;
        if (term && websocketRef.current?.readyState === WebSocket.OPEN) {
          const dimensions = { cols: term.cols, rows: term.rows };
          websocketRef.current.send(JSON.stringify({ type: 'resize', ...dimensions }));
        }
      } catch (err) {
        console.error('Error resizing terminal:', err);
      }
    }
  }, []);

  useEffect(() => {
    if (!terminalRef.current) return;

    const term = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: {
        background: '#1e1e1e',
        foreground: '#ffffff',
        cursor: '#ffffff',
        selectionBackground: 'rgba(255, 255, 255, 0.3)',
        black: '#000000',
        red: '#e06c75',
        green: '#98c379',
        yellow: '#d19a66',
        blue: '#61afef',
        magenta: '#c678dd',
        cyan: '#56b6c2',
        white: '#ffffff',
      },
      allowTransparency: true,
      scrollback: 10000,
    });

    term.open(terminalRef.current);
    xtermRef.current = term;

    const fitAddon = new FitAddon();
    fitAddonRef.current = fitAddon;
    term.loadAddon(fitAddon);
    setTimeout(() => fitAddon.fit(), 100);

    try {
      const webglAddon = new WebglAddon();
      webglAddonRef.current = webglAddon;
      term.loadAddon(webglAddon);
    } catch (e) {
      console.warn('WebGL addon could not be loaded:', e);
    }

    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      console.error('No authentication token found');
      term.writeln('\r\nError: No authentication token found');
      return;
    }

    const baseUrl = apiBaseUrl.replace(/\/$/, '').replace(/\/api\/v1$/, '');
    const wsBaseUrl = baseUrl.replace(/^http/, 'ws');
    const wsUrl = `${wsBaseUrl}/api/v1/ssh/ws/ssh/${vmId}?token=${token}`;
    const ws = new WebSocket(wsUrl);
    websocketRef.current = ws;

    ws.onopen = () => {
      const dimensions = { cols: term.cols, rows: term.rows };
      ws.send(JSON.stringify({ type: 'resize', ...dimensions }));

      term.onData((data) => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            type: 'input',
            data: data
          }));
        }
      });

      term.onResize((size) => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            type: 'resize',
            cols: size.cols,
            rows: size.rows
          }));
        }
      });

      term.writeln('Connected to remote server...');
    };

    ws.onmessage = (event) => {
      if (typeof event.data === 'string') {
        term.write(event.data);
      } else if (event.data instanceof Blob) {
        const reader = new FileReader();
        reader.onload = () => {
          const text = reader.result?.toString();
          if (text) term.write(text);
        };
        reader.readAsText(event.data);
      }
    };

    ws.onclose = (event) => {
      term.writeln(`\r\nConnection closed (${event.code}): ${event.reason || 'Unknown reason'}`);
      term.writeln('\r\nPress Ctrl+R to refresh and try again.');
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      term.writeln(`\r\nWebSocket error occurred. Check console for details.`);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (webglAddonRef.current) webglAddonRef.current.dispose();
      term.dispose();
      if (ws.readyState === WebSocket.OPEN) ws.close();
    };
  }, [vmId, apiBaseUrl, handleResize]);

  return (
    <div
      ref={terminalRef}
      style={{
        height: '100%',
        minHeight: '400px',
        width: '100%',
        padding: '0',
        backgroundColor: '#1e1e1e',
        borderRadius: '4px',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column'
      }}
    />
  );
};

export const SSHTerminal: React.FC<SSHTerminalProps> = (props) => (
  <ErrorBoundary>
    <TerminalComponent {...props} />
  </ErrorBoundary>
);

export default SSHTerminal;
