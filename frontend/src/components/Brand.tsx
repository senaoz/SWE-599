/** The app's logo and name, used in the header and on the sign-in pages. */
export default function Brand({ href = "/" }: { href?: string }) {
  return (
    <a
      href={href}
      aria-label="Scholar Radar, home"
      className="flex items-center gap-2.5 rounded-xs outline-focus-ring focus-visible:outline-2 focus-visible:outline-offset-2"
    >
      <img src="/boun-logo.png" alt="" className="size-8 rounded-md" />
      <span className="text-lg font-bold tracking-tight text-primary">Scholar Radar</span>
    </a>
  );
}
