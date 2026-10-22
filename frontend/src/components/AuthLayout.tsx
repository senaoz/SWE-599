import type { ReactNode } from "react";
import Brand from "./Brand";

interface AuthLayoutProps {
  title: string;
  subtitle: string;
  error: string | null;
  children: ReactNode;
  footer: ReactNode;
}

/** Shared layout of the sign-in and sign-up pages: form on the left, image on the right. */
export default function AuthLayout({ title, subtitle, error, children, footer }: AuthLayoutProps) {
  return (
    <section className="grid min-h-screen bg-primary lg:grid-cols-2">
      <div className="relative flex w-full flex-1 flex-col bg-primary">
        <header className="px-4 pt-8 md:px-8">
          <Brand href="/login" />
        </header>

        <div className="flex flex-1 justify-center px-4 py-12 md:items-center md:px-8 md:py-0">
          <div className="flex w-full flex-col gap-8 sm:max-w-[360px]">
            <div className="flex flex-col gap-2 lg:gap-3">
              <h1 className="text-xl font-semibold text-primary md:text-display-xs">{title}</h1>
              <p className="text-md text-tertiary">{subtitle}</p>
            </div>

            {error && (
              <div className="rounded-lg bg-error-primary px-4 py-3 text-sm text-error-primary ring-1 ring-error_subtle">
                {error}
              </div>
            )}

            {children}

            <div className="flex justify-center gap-1 text-center text-sm">{footer}</div>
          </div>
        </div>

        <footer className="hidden p-8 lg:block">
          <p className="text-sm text-tertiary">Boğaziçi University · SWE 599</p>
        </footer>
      </div>

      <figure
        className="relative hidden flex-1 overflow-hidden rounded-l-[80px] lg:flex"
        style={{ background: "linear-gradient(135deg, #3b1f7a 0%, #53389E 40%, #6941C6 100%)" }}
      >
        <img
          src="/login-bg.jpg"
          alt=""
          className="pointer-events-none absolute inset-0 h-full w-full object-cover"
        />
        <div className="pointer-events-none absolute inset-0 bg-linear-to-t from-black/50 from-20% to-transparent to-90%" />
      </figure>
    </section>
  );
}
