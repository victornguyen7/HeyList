"use client";

import Link from "next/link";
import { useState } from "react";
import { supabase, useSession } from "../auth";
import { button, buttonGlass, card } from "../ui";

// Optional email login. Logged in, you join any list in one tap, as the same person on every device.
export default function Login() {
  const session = useSession();
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    // Back to the page that sent you here (?next=/lists/<id>); only a path on this site.
    const next = new URLSearchParams(window.location.search).get("next");
    const path = next?.startsWith("/") && !next.startsWith("//") ? next : "/";
    const { error } = await supabase.auth.signInWithOtp({ email, options: { emailRedirectTo: window.location.origin + path } });
    setStatus(error ? `Could not send the link: ${error.message}` : `Check ${email} for a login link.`);
  }

  return (
    <main className={`${card} mx-auto flex w-full max-w-md flex-col gap-4 lg:mt-16 lg:max-w-[440px] lg:p-8`}>
      <h1 className="text-[28px] tracking-[-0.015em]">Log in</h1>
      {session ? (
        <>
          <p className="text-base">You are logged in as {session.user.email}.</p>
          <div className="flex gap-2">
            <Link href="/" className={button}>
              Your lists
            </Link>
            <button type="button" className={buttonGlass} onClick={() => supabase.auth.signOut()}>
              Log out
            </button>
          </div>
        </>
      ) : (
        <form onSubmit={send} className="flex flex-col gap-3">
          <p className="text-base text-muted">We email you a link; no password. You can still join lists as a guest without one.</p>
          <input
            className="h-12 rounded-[20px] bg-bg px-4 text-base"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            aria-label="Email"
            autoComplete="email"
            required
          />
          <button type="submit" className={button}>
            Email me a link
          </button>
        </form>
      )}
      {status && <p role="status" className="text-base">{status}</p>}
    </main>
  );
}
