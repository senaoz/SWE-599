import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Mail01, Lock01 } from "@untitledui/icons";
import { Button } from "@/components/base/buttons/button";
import { Input } from "@/components/base/input/input";
import AuthLayout from "../components/AuthLayout";

interface Props {
  onRegister: (email: string, password: string) => Promise<void>;
}

export default function RegisterPage({ onRegister }: Props) {
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
      await onRegister(email, password);
      navigate("/");
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setError(axiosErr.response?.data?.detail ?? "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      title="Create an account"
      subtitle="Follow institutions and see which Boğaziçi researchers work on their new papers."
      error={error}
      footer={
        <>
          <span className="text-tertiary">Already have an account?</span>
          <Link to="/login" className="font-semibold text-brand-secondary hover:text-brand-secondary_hover">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="flex flex-col gap-6">
        <div className="flex flex-col gap-5">
          <Input
            label="Email"
            type="email"
            placeholder="you@example.com"
            icon={Mail01}
            value={email}
            onChange={(v) => setEmail(v)}
            isRequired
          />
          <Input
            label="Password"
            type="password"
            placeholder="At least 8 characters"
            icon={Lock01}
            hint="Must be at least 8 characters"
            value={password}
            onChange={(v) => setPassword(v)}
            minLength={8}
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
          Create account
        </Button>
      </form>
    </AuthLayout>
  );
}
