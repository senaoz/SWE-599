import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./hooks/useAuth";
import NavBar from "./components/NavBar";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import DashboardPage from "./pages/DashboardPage";
import InstitutionsPage from "./pages/InstitutionsPage";
import AdminPage from "./pages/AdminPage";
import ResearchersPage from "./pages/ResearchersPage";

function ProtectedLayout({ onLogout }: { onLogout: () => void }) {
  return (
    <>
      <NavBar onLogout={onLogout} />
      <main className="bg-secondary" style={{ minHeight: "calc(100vh - 52px)" }}>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/institutions" element={<InstitutionsPage />} />
          <Route path="/researchers" element={<ResearchersPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </>
  );
}

export default function App() {
  const { isAuthenticated, login, register, logout } = useAuth();

  return (
    <BrowserRouter>
      {isAuthenticated ? (
        <ProtectedLayout onLogout={logout} />
      ) : (
        <Routes>
          <Route path="/login" element={<LoginPage onLogin={login} />} />
          <Route
            path="/register"
            element={<RegisterPage onRegister={register} />}
          />
          <Route path="*" element={<Navigate to="/login" />} />
        </Routes>
      )}
    </BrowserRouter>
  );
}
