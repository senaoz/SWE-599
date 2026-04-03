import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Mail01, Lock01 } from "@untitledui/icons";
import { Button } from "@/components/base/buttons/button";
import { Input } from "@/components/base/input/input";

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
    <div className="flex min-h-screen items-center justify-center bg-secondary px-4">
      <div className="w-full max-w-sm rounded-2xl bg-primary p-8 shadow-xl ring-1 ring-primary">
        <div className="mb-6">
          <h1 className="text-display-xs font-semibold text-primary">Create account</h1>
          <p className="mt-1 text-sm text-tertiary">Get started with BOUN Paper Recommender</p>
        </div>

        {error && (
          <div className="mb-4 rounded-lg bg-error-primary px-4 py-3 text-sm text-error-primary ring-1 ring-error_subtle">
            {error}
          </div>
        )}

        <form onSubmit={submit} className="flex flex-col gap-5">
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
            placeholder="Min 8 characters"
            icon={Lock01}
            hint="Must be at least 8 characters"
            value={password}
            onChange={(v) => setPassword(v)}
            minLength={8}
            isRequired
          />

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

        <p className="mt-6 text-center text-sm text-tertiary">
          Already have an account?{" "}
          <Link to="/login" className="font-semibold text-brand-secondary hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
