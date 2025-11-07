// frontend/src/App.tsx
import { authApi } from "./lib/api";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";

export default function App() {
  // If there’s no session yet, render a full-screen login
  if (!authApi.isAuthed) {
    return <LoginPage />;
  }

  // Once authed, show the app (dashboard/shell/etc.)
  return <DashboardPage />;
}