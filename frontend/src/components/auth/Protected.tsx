import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import LoginPage from "../../pages/LoginPage";
import { authApi } from "../../lib/api";

type ProtectedProps = {
  children: ReactNode;
};

const REQUIRE_AUTH =
  (import.meta.env.VITE_REQUIRE_AUTH ?? "true").toString().toLowerCase() !==
  "false";

const BYPASS_EMAIL =
  import.meta.env.VITE_BYPASS_EMAIL || import.meta.env.VITE_DEMO_EMAIL || "demo@example.com";
const BYPASS_PASSWORD =
  import.meta.env.VITE_BYPASS_PASSWORD ||
  import.meta.env.VITE_DEMO_PASSWORD ||
  "demo123";

export function Protected({ children }: ProtectedProps) {
  const browser =
    typeof window !== "undefined" && typeof window.document !== "undefined";
  const cypressFlag = browser && Boolean((window as any)?.Cypress);
  const urlBypass =
    browser &&
    new URLSearchParams(window.location.search).get("auth") === "off";

  const bypass = !REQUIRE_AUTH || cypressFlag || urlBypass;

  const [isAuthed, setIsAuthed] = useState<boolean>(authApi.isAuthed);
  const [bypassReady, setBypassReady] = useState(!bypass);
  const [autoAuthFailed, setAutoAuthFailed] = useState(false);

  const handleLoggedIn = useCallback(() => {
    setIsAuthed(true);
  }, []);

  // Keep state in sync when the user logs in/out via another tab
  useEffect(() => {
    if (bypass) return;
    const syncFromStorage = () => setIsAuthed(authApi.isAuthed);
    window.addEventListener("storage", syncFromStorage);
    return () => window.removeEventListener("storage", syncFromStorage);
  }, [bypass]);

  // When bypassing auth (dev/Cypress), automatically acquire tokens so API calls succeed.
  useEffect(() => {
    if (!bypass) {
      setBypassReady(true);
      return;
    }

    let alive = true;
    const bootstrap = async () => {
      try {
        if (!authApi.isAuthed) {
          try {
            await authApi.login(BYPASS_EMAIL, BYPASS_PASSWORD);
          } catch {
            // If demo user doesn't exist yet, create it on the fly.
            await authApi.signup(BYPASS_EMAIL, BYPASS_PASSWORD);
          }
        }
        if (alive) {
          setIsAuthed(true);
        }
      } catch (err) {
        console.warn("Auto auth failed; falling back to manual login.", err);
        if (alive) {
          setAutoAuthFailed(true);
        }
      } finally {
        if (alive) {
          setBypassReady(true);
        }
      }
    };

    bootstrap();
    return () => {
      alive = false;
    };
  }, [bypass]);

  if (bypass) {
    if (!bypassReady) return null;
    if (autoAuthFailed) {
      return <LoginPage onSuccess={handleLoggedIn} />;
    }
    return <>{children}</>;
  }

  if (!isAuthed) {
    return <LoginPage onSuccess={handleLoggedIn} />;
  }

  return <>{children}</>;
}
