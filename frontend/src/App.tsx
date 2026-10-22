import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./hooks/useAuth";
import NavBar from "./components/NavBar";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import DashboardPage from "./pages/DashboardPage";
import InstitutionsPage from "./pages/InstitutionsPage";
import AdminPage from "./pages/AdminPage";
import ResearchersPage from "./pages/ResearchersPage";
import ResearcherDetailPage from "./pages/ResearcherDetailPage";

function ProtectedLayout({ onLogout }: { onLogout: () => void }) {
  return (
    <div className="flex min-h-screen flex-col bg-secondary">
      <div className="sticky top-0 z-40">
        <NavBar onLogout={onLogout} />
      </div>
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/institutions" element={<InstitutionsPage />} />
          <Route path="/researchers" element={<ResearchersPage />} />
          <Route path="/researchers/:id" element={<ResearcherDetailPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </div>
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
