import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Input } from "@/components/base/input/input";
import { Button } from "@/components/base/buttons/button";
import AuthLayout from "../components/AuthLayout";

interface Props {
  onLogin: (email: string, password: string) => Promise<void>;
}

export default function LoginPage({ onLogin }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await onLogin(email, password);
      navigate("/");
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setError(axiosErr.response?.data?.detail ?? "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to see new papers and the Boğaziçi researchers who work on them."
      error={error}
      footer={
        <>
          <span className="text-tertiary">Don't have an account?</span>
          <Link to="/register" className="font-semibold text-brand-secondary hover:text-brand-secondary_hover">
            Sign up
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="flex flex-col gap-6">
        <div className="flex flex-col gap-5">
          <Input
            label="Email"
            type="email"
            placeholder="Enter your email"
            value={email}
            onChange={(v) => setEmail(v)}
            isRequired
          />
          <Input
            label="Password"
            type="password"
            placeholder="••••••••"
            value={password}
            onChange={(v) => setPassword(v)}
            isRequired
          />
        </div>
        <Button
          type="submit"
          color="primary"
          size="md"
          isLoading={loading}
          isDisabled={loading}
          className="w-full justify-center"
        >
          Sign in
        </Button>
      </form>
    </AuthLayout>
  );
}
