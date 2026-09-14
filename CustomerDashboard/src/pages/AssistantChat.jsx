import { useState } from "react";
import { sendAssistantMessage } from "../api";
import "./AssistantChat.css";

// Lab AI3 -- bounded history: only the last 8 turns are sent with each
// request, so cost and context stay predictable regardless of how long the
// conversation runs (this must match config.ASSISTANT_MAX_HISTORY_TURNS).
const MAX_HISTORY_TURNS = 8;

const STARTER_QUESTIONS = [
  "What's our overall churn rate?",
  "Which 5 customers are highest risk right now?",
  "What would the risk score be for a new month-to-month customer paying $95/mo?",
];

function AssistantChat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const send = async (text) => {
    const question = (text ?? input).trim();
    if (!question || loading) return;

    setError("");
    setInput("");
    const nextMessages = [...messages, { role: "user", content: question }];
    setMessages(nextMessages);
    setLoading(true);

    try {
      const history = nextMessages
        .slice(0, -1)
        .slice(-MAX_HISTORY_TURNS)
        .map((m) => ({ role: m.role, content: m.content }));

      const data = await sendAssistantMessage(question, history);

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.reply, toolCalls: data.tool_calls || [] },
      ]);
    } catch (err) {
      console.error(err);
      setError(err.message || "The assistant didn't respond -- try again.");
    } finally {
      setLoading(false);
    }
  };

  const retryLast = () => {
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (lastUser) send(lastUser.content);
  };

  return (
    <div className="assistant-container">
      <div className="header-section">
        <h2>Retention Assistant</h2>
        <p className="description">
          Ask about churn trends, a specific customer, or a hypothetical prediction.
          Every answer shows which tools produced it.
        </p>
      </div>

      <div className="chat-window">
        {messages.length === 0 && (
          <div className="starter-questions">
            {STARTER_QUESTIONS.map((q) => (
              <button key={q} className="starter-chip" onClick={() => send(q)}>
                {q}
              </button>
            ))}
          </div>
        )}

        {messages.map((m, idx) => (
          <div key={idx} className={`chat-message ${m.role}`}>
            <div className="chat-bubble">{m.content}</div>
            {m.toolCalls && m.toolCalls.length > 0 && (
              <div className="tool-trail">
                {m.toolCalls.map((t, i) => (
                  <span key={i} className="tool-chip" title={JSON.stringify(t.args)}>
                    🔧 {t.tool}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="chat-message assistant">
            <div className="chat-bubble typing">Thinking…</div>
          </div>
        )}
      </div>

      {error && (
        <div className="error-message">
          ⚠️ {error}
          <button className="btn btn-secondary retry-btn" onClick={retryLast}>
            Retry
          </button>
        </div>
      )}

      <form
        className="chat-input-row"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <input
          id="assistant-chat-input"
          type="text"
          value={input}
          placeholder="Ask about a customer, a segment, or a churn scenario…"
          onChange={(e) => setInput(e.target.value)}
          disabled={loading}
        />
        <button type="submit" className="btn btn-primary" disabled={loading || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}

export default AssistantChat;
