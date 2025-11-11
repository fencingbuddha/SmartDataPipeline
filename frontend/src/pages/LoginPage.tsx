import { useState } from "react";
import type { CSSProperties, FormEvent } from "react";
import { authApi } from "../lib/api";
import { Card, Text } from "../ui";

type LoginPageProps = { onSuccess?: () => void };

export default function LoginPage({ onSuccess }: LoginPageProps) {
  const [email, setEmail] = useState("demo@example.com");
  const [password, setPassword] = useState("demo123");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (evt: FormEvent<HTMLFormElement>) => {
    evt.preventDefault();
    setError(null);

    const e = email.trim();
    if (!e || !password) {
      setError("Email and password are required.");
      return;
    }

    setLoading(true);
    try {
      await authApi.login(e, password);
      // Re-render the app if no callback was provided
      if (onSuccess) {
        onSuccess();
      } else {
        window.location.reload();
      }
    } catch (err) {
      const msg =
        err instanceof Error ? err.message :
        typeof err === "string" ? err : "Login failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleSignup = async () => {
    setError(null);

    const e = email.trim();
    if (!e || !password) {
      setError("Email and password are required.");
      return;
    }

    setLoading(true);
    try {
      await authApi.signup(e, password);
      if (onSuccess) {
        onSuccess();
      } else {
        window.location.reload();
      }
    } catch (err) {
      const msg =
        err instanceof Error ? err.message :
        typeof err === "string" ? err : "Sign up failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      /* Pin to viewport so it can't be squeezed by parent layout */
      style={{
        position: "fixed",
        inset: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "radial-gradient(circle at top, #1c1c1c, #050505)",
        padding: 32
      }}
    >
      <Card style={{ width: "min(96vw, 760px)", padding: 24 }}>
        <Text
          variant="h2"
          style={{ marginBottom: 16 }}
          data-testid="login-title"
        >
          Sign in
        </Text>
        <form onSubmit={handleSubmit} style={gridForm}>
          {/* Row 1: inputs */}
          <label className="sd-stack sd-gap-2" style={{ gridColumn: "1 / 2" }}>
            <Text variant="small">Email</Text>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              style={inputStyle}
              placeholder="you@example.com"
              autoComplete="username"
            />
          </label>

          <label className="sd-stack sd-gap-2" style={{ gridColumn: "2 / 3" }}>
            <Text variant="small">Password</Text>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              style={inputStyle}
              placeholder="password"
              autoComplete="current-password"
            />
          </label>

          {/* Row 2: buttons aligned under each input */}
          <div style={{ gridColumn: "1 / 2", display: "flex", justifyContent: "center" }}>
            <button
              type="submit"
              className="sd-btn"
              disabled={loading}
              aria-busy={loading}
            >
              {loading ? "Signing in…" : "Log In"}
            </button>
          </div>

          <div style={{ gridColumn: "2 / 3", display: "flex", justifyContent: "center" }}>
            <button
              type="button"
              className="sd-btn ghost"
              onClick={handleSignup}
              disabled={loading}
              aria-busy={loading}
            >
              Sign Up
            </button>
          </div>

          {/* Full-width error under the grid if present */}
          {error && (
            <Text variant="small" style={{ gridColumn: "1 / -1", color: "#ff7b7b", marginTop: 8 }}>
              {error}
            </Text>
          )}
        </form>
      </Card>
    </div>
  );
}

const inputStyle: CSSProperties = {
  width: "100%",
  padding: "10px 12px",
  borderRadius: 8,
  border: "1px solid #2d3755",
  background: "#0c1120",
  color: "#e4e9ff",
  fontSize: 14
};

const gridForm: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr",
  columnGap: 24,
  rowGap: 16,
  alignItems: "center",
};
