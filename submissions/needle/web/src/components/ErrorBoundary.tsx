import { Component, type ReactNode } from "react";

/* Last line of defence: a render error shows a calm panel instead of a blank page. Same form as ErrorState in ui.tsx. */
export default class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: unknown) {
    return { error: error instanceof Error ? error : new Error(String(error)) };
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <div className="mx-auto max-w-[1600px] px-4 pt-6 pb-16 sm:px-6 lg:px-8">
        <div role="alert" className="panel fade-in border-l-[3px] border-l-affected p-4">
          <p className="font-semibold">Something went wrong drawing this view.</p>
          <p className="mt-1 font-mono text-xs break-words text-ink-2">{error.message || error.name}</p>
          <button className="btn btn-quiet mt-3" onClick={() => window.location.reload()}>Reload</button>
        </div>
      </div>
    );
  }
}
