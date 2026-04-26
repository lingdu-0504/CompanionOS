import React from 'react';

interface Props {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', padding: 40, color: '#e74c3c' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>⚠</div>
          <h2 style={{ margin: '0 0 8px', color: '#fff' }}>页面渲染异常</h2>
          <p style={{ margin: '0 0 16px', color: '#888', fontSize: 13, textAlign: 'center', maxWidth: 400 }}>
            {this.state.error?.message || '未知错误'}
          </p>
          <button onClick={this.handleRetry} style={{ padding: '8px 24px', background: '#6c5ce7', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 14 }}>
            重试
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
