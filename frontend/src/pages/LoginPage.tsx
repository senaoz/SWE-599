import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Input } from "@/components/base/input/input";
import { Button } from "@/components/base/buttons/button";

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
    <section className="grid min-h-screen bg-primary lg:grid-cols-2">
      {/* Left column */}
      <div className="relative flex w-full flex-1 flex-col bg-primary">
        {/* Desktop header */}
        <header className="absolute top-0 left-0 hidden p-8 lg:block">
          <div className="flex items-center gap-2">
            <div className="flex size-8 items-center justify-center rounded-lg bg-brand-solid">
              <svg viewBox="0 0 16 16" fill="none" className="size-4 text-white">
                <path d="M8 2L2 5.5V10.5L8 14L14 10.5V5.5L8 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
                <path d="M8 2V14M2 5.5L14 10.5M14 5.5L2 10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </div>
            <span className="text-md font-semibold text-primary">BOUN Papers</span>
          </div>
        </header>

        {/* Form area */}
        <div className="flex flex-1 justify-center px-4 py-12 md:items-center md:px-8 md:py-0">
          <div className="flex w-full flex-col gap-8 sm:max-w-[360px]">
            <div className="flex flex-col gap-6">
              {/* Mobile logo */}
              <div className="flex items-center gap-2 lg:hidden">
                <div className="flex size-8 items-center justify-center rounded-lg bg-brand-solid">
                  <svg viewBox="0 0 16 16" fill="none" className="size-4 text-white">
                    <path d="M8 2L2 5.5V10.5L8 14L14 10.5V5.5L8 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
                    <path d="M8 2V14M2 5.5L14 10.5M14 5.5L2 10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  </svg>
                </div>
                <span className="text-md font-semibold text-primary">BOUN Papers</span>
              </div>
              <div className="flex flex-col gap-2 lg:gap-3">
                <h1 className="text-xl font-semibold text-primary md:text-display-xs">Welcome back</h1>
                <p className="text-md text-tertiary">Welcome back! Please enter your details.</p>
              </div>
            </div>

            {error && (
              <div className="rounded-lg bg-error-primary px-4 py-3 text-sm text-error-primary ring-1 ring-error_subtle">
                {error}
              </div>
            )}

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
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(v) => setPassword(v)}
                  isRequired
                />
              </div>

              {/* Remember me + Forgot password */}
              <div className="flex items-center justify-between">
                <label className="flex cursor-pointer items-center gap-2">
                  <input
                    type="checkbox"
                    name="remember"
                    className="size-4 rounded border border-primary accent-brand-solid"
                  />
                  <span className="select-none text-sm font-medium text-secondary">Remember for 30 days</span>
                </label>
                <span className="cursor-not-allowed text-sm font-semibold text-brand-secondary opacity-60">
                  Forgot password
                </span>
              </div>

              <div className="flex flex-col gap-4">
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

                <button
                  type="button"
                  disabled
                  className="flex w-full cursor-not-allowed items-center justify-center gap-2.5 rounded-lg bg-primary px-4 py-2.5 text-md font-semibold text-secondary opacity-50 shadow-xs ring-1 ring-primary ring-inset transition duration-100"
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path d="M23.766 12.2764C23.766 11.4607 23.6999 10.6406 23.5588 9.83807H12.24V14.4591H18.7217C18.4528 15.9494 17.5885 17.2678 16.323 18.1056V21.1039H20.19C22.4608 19.0139 23.766 15.9274 23.766 12.2764Z" fill="#4285F4" />
                    <path d="M12.24 24.0008C15.4764 24.0008 18.2058 22.9382 20.1944 21.1039L16.3274 18.1055C15.2516 18.8375 13.8626 19.252 12.2444 19.252C9.11376 19.252 6.45934 17.1399 5.50693 14.3003H1.51648V17.3912C3.55359 21.4434 7.70278 24.0008 12.24 24.0008Z" fill="#34A853" />
                    <path d="M5.50253 14.3003C4.99987 12.8099 4.99987 11.1961 5.50253 9.70575V6.61481H1.51649C-0.18551 10.0056 -0.18551 14.0004 1.51649 17.3912L5.50253 14.3003Z" fill="#FBBC04" />
                    <path d="M12.24 4.74966C13.9508 4.7232 15.6043 5.36697 16.8433 6.54867L20.2694 3.12262C18.1 1.0855 15.2207 -0.034466 12.24 0.000808666C7.70277 0.000808666 3.55359 2.55822 1.51648 6.61481L5.50252 9.70575C6.45052 6.86173 9.10935 4.74966 12.24 4.74966Z" fill="#EA4335" />
                  </svg>
                  Sign in with Google
                </button>
              </div>
            </form>

            <div className="flex justify-center gap-1 text-center">
              <span className="text-sm text-tertiary">Don't have an account?</span>
              <Link
                to="/register"
                className="text-sm font-semibold text-brand-secondary hover:text-brand-secondary_hover"
              >
                Sign up
              </Link>
            </div>
          </div>
        </div>

        {/* Desktop footer */}
        <footer className="absolute bottom-0 left-0 hidden p-8 lg:block">
          <p className="text-sm text-tertiary">© BOUN Paper Recommender 2025</p>
        </footer>
      </div>

      {/* Right column */}
      <figure className="relative hidden flex-1 flex-col items-start justify-end gap-6 overflow-hidden rounded-l-[80px] p-14 lg:flex" style={{ background: "linear-gradient(135deg, #3b1f7a 0%, #53389E 40%, #6941C6 100%)" }}>
        <div className="pointer-events-none absolute inset-0 bg-linear-to-t from-black/40 from-20% to-transparent to-90%" />
        <blockquote className="relative z-10 text-display-md font-medium text-white">
          "Discover relevant academic research tailored to your institution's expertise — automatically."
        </blockquote>
        <figcaption className="relative z-10 flex w-full flex-col gap-3">
          <p className="text-xl font-semibold text-white md:text-display-xs">Research Discovery</p>
          <div className="flex w-full gap-3">
            <div className="flex w-full flex-col gap-0.5">
              <p className="text-lg font-semibold text-white not-italic">Automated Paper Recommendations</p>
              <p className="text-md font-medium text-white/80 not-italic">Boğaziçi University</p>
            </div>
          </div>
        </figcaption>
      </figure>
    </section>
  );
}
