import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App.jsx";
import "./styles.css";

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <main className="min-h-screen bg-panel p-6 text-ink">
          <div className="mx-auto max-w-3xl rounded-md border border-coral/30 bg-white p-5 shadow-soft">
            <h1 className="text-lg font-semibold text-coral">Dashboard failed to load</h1>
            <pre className="mt-3 overflow-auto rounded-md bg-panel p-3 text-xs">
              {this.state.error.message}
            </pre>
          </div>
        </main>
      );
    }

    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
);
