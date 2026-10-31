"use client";

import Link from "next/link";
import { useState } from "react";
import { accountName, supabase, useSession } from "../auth";
import { button, buttonGlass, card, field } from "../ui";

// Email and password accounts (Supabase Auth). Sign up and "forgot password" are confirmed with a code
// sent to the email; the emails come from the owner's address (Supabase custom SMTP, see docs/AUTH.md).
// Logged in, you join any list in one tap, as the same person on every device. Guests still join by name.
type Step = "login" | "signup" | "verify" | "forgot" | "reset" | "newPassword";

const MIN_PASSWORD = 8;

// Back to the page that sent you here (?next=/lists/<id>); only a path on this site.
function nextPath() {
  const next = new URLSearchParams(window.location.search).get("next");
  return next?.startsWith("/") && !next.startsWith("//") ? next : "/";
}

export default function Login() {
  const session = useSession();
  const [step, setStep] = useState<Step>("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // The name every list you open joins you as; null until edited, so it shows the saved one.
  const [newName, setNewName] = useState<string | null>(null);

  function go(next: Step, message: string | null = null) {
    setStep(next);
    setCode("");
    setStatus(message);
  }

  // Runs one auth call with the button disabled; a thrown or returned error is shown as the status.
  async function run(e: React.FormEvent, action: () => Promise<void>) {
    e.preventDefault();
    setBusy(true);
    setStatus(null);
    try {
      await action();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const logIn = (e: React.FormEvent) =>
    run(e, async () => {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error?.code === "email_not_confirmed") {
        await supabase.auth.resend({ type: "signup", email });
        return go("verify", `Your email isn't confirmed yet. We sent a new code to ${email}.`);
      }
      if (error) throw new Error(error.code === "invalid_credentials" ? "Wrong email or password." : error.message);
      window.location.assign(nextPath());
    });

  const signUp = (e: React.FormEvent) =>
    run(e, async () => {
      const { data, error } = await supabase.auth.signUp({ email, password, options: { data: { name: name.trim() } } });
      if (error) throw error;
      // Supabase answers a sign-up for a taken email with a user that has no identities, and sends nothing.
      if (data.user?.identities?.length === 0) return go("login", "An account with this email already exists. Log in instead.");
      // No session means the project asks for email confirmation, so the code is on its way.
      if (!data.session) return go("verify", `We sent a code to ${email}. Enter it to finish signing up.`);
      window.location.assign(nextPath());
    });

  const verify = (e: React.FormEvent) =>
    run(e, async () => {
      const { error } = await supabase.auth.verifyOtp({ email, token: code.trim(), type: "signup" });
      if (error) throw new Error("That code is wrong or has expired. Check the latest email, or send a new code.");
      window.location.assign(nextPath());
    });

  const sendReset = (e: React.FormEvent) =>
    run(e, async () => {
      const { error } = await supabase.auth.resetPasswordForEmail(email);
      if (error) throw error;
      // Sent whether or not the account exists, so nobody can probe which emails have accounts.
      go("reset", `If ${email} has an account, we sent it a code.`);
    });

  const checkReset = (e: React.FormEvent) =>
    run(e, async () => {
      const { error } = await supabase.auth.verifyOtp({ email, token: code.trim(), type: "recovery" });
      if (error) throw new Error("That code is wrong or has expired. Check the latest email, or send a new code.");
      setPassword("");
      go("newPassword");
    });

  const savePassword = (e: React.FormEvent) =>
    run(e, async () => {
      const { error } = await supabase.auth.updateUser({ password });
      if (error) throw error;
      window.location.assign(nextPath());
    });

  const saveName = (e: React.FormEvent) =>
    run(e, async () => {
      const { error } = await supabase.auth.updateUser({ data: { name: newName!.trim() } });
      if (error) throw error;
      setNewName(null);
      setStatus("Saved. Lists you join from now on use this name.");
    });

  const resend = () => {
    setBusy(true);
    const sent = step === "verify" ? supabase.auth.resend({ type: "signup", email }) : supabase.auth.resetPasswordForEmail(email);
    sent
      .then(({ error }) => setStatus(error ? error.message : `We sent a new code to ${email}.`))
      .finally(() => setBusy(false));
  };

  const emailInput = (
    <input className={field} type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" aria-label="Email" autoComplete="email" required />
  );
  const passwordInput = (autoComplete: "current-password" | "new-password", label = "Password") => (
    <input
      className={field}
      type="password"
      value={password}
      onChange={(e) => setPassword(e.target.value)}
      placeholder={label}
      aria-label={label}
      autoComplete={autoComplete}
      minLength={autoComplete === "new-password" ? MIN_PASSWORD : undefined}
      required
    />
  );
  const codeInput = (
    <input
      className={`${field} tracking-[0.3em]`}
      value={code}
      onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
      placeholder="123456"
      aria-label="Code from the email"
      inputMode="numeric"
      autoComplete="one-time-code"
      pattern="\d{6,10}"
      maxLength={10}
      required
    />
  );
  const linkButton = "self-start text-[15px] text-ai disabled:opacity-40";

  // The way back on phones, which have no top bar (Figma "12 · Log in").
  const backLink = (
    <Link href="/" className="text-base font-medium text-muted-on-bg lg:hidden">
      ← Lists
    </Link>
  );

  if (session && step !== "newPassword") {
    return (
      <>
      {backLink}
      <main className={`${card} mx-auto flex w-full max-w-md flex-col gap-4 lg:mt-16 lg:max-w-[440px] lg:p-8`}>
        <h1 className="text-[28px] tracking-[-0.015em]">Your account</h1>
        <p className="text-base">You are logged in as {session.user.email}.</p>
        <form onSubmit={saveName} className="flex gap-2">
          <input
            className={`${field} min-w-0 flex-1`}
            value={newName ?? accountName(session) ?? ""}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Your name"
            aria-label="Your name"
            autoComplete="name"
            maxLength={40}
            required
          />
          <button type="submit" className={`${buttonGlass} px-5`} disabled={busy || newName === null || !newName.trim()}>
            Save
          </button>
        </form>
        <div className="flex gap-2">
          <Link href="/" className={button}>
            Your lists
          </Link>
          <button type="button" className={buttonGlass} onClick={() => supabase.auth.signOut()}>
            Log out
          </button>
        </div>
        {status && (
          <p role="status" className="text-base">
            {status}
          </p>
        )}
      </main>
      </>
    );
  }

  const title = { login: "Log in", signup: "Create an account", verify: "Check your email", forgot: "Reset your password", reset: "Check your email", newPassword: "Choose a new password" }[step];

  return (
    <>
    {backLink}
    <main className={`${card} mx-auto flex w-full max-w-md flex-col gap-4 lg:mt-16 lg:max-w-[440px] lg:p-8`}>
      <h1 className="text-[28px] tracking-[-0.015em]">{title}</h1>

      {(step === "login" || step === "signup") && (
        <div className="grid grid-cols-2 gap-1 rounded-[30px] bg-bg p-1" role="tablist">
          {(["login", "signup"] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              role="tab"
              aria-selected={step === tab}
              onClick={() => go(tab)}
              className={`h-10 rounded-[26px] text-[15px] font-medium ${step === tab ? "bg-surface-2 text-text" : "text-muted"}`}
            >
              {tab === "login" ? "Log in" : "Sign up"}
            </button>
          ))}
        </div>
      )}

      {step === "login" && (
        <form onSubmit={logIn} className="flex flex-col gap-3">
          {emailInput}
          {passwordInput("current-password")}
          <button type="submit" className={button} disabled={busy}>
            Log in
          </button>
          <button type="button" className={linkButton} onClick={() => go("forgot")}>
            Forgot your password?
          </button>
        </form>
      )}

      {step === "signup" && (
        <form onSubmit={signUp} className="flex flex-col gap-3">
          <p className="text-base text-muted">Your name is how friends see you on every list. You can still join lists as a guest without an account.</p>
          <input className={field} value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" aria-label="Your name" autoComplete="name" maxLength={40} required />
          {emailInput}
          {passwordInput("new-password", `Password (at least ${MIN_PASSWORD} characters)`)}
          <button type="submit" className={button} disabled={busy}>
            Sign up
          </button>
        </form>
      )}

      {(step === "verify" || step === "reset") && (
        <form onSubmit={step === "verify" ? verify : checkReset} className="flex flex-col gap-3">
          {codeInput}
          <button type="submit" className={button} disabled={busy}>
            {step === "verify" ? "Confirm email" : "Continue"}
          </button>
          <div className="flex justify-between">
            <button type="button" className={linkButton} onClick={resend} disabled={busy}>
              Send a new code
            </button>
            <button type="button" className={linkButton} onClick={() => go(step === "verify" ? "signup" : "forgot")}>
              Use another email
            </button>
          </div>
        </form>
      )}

      {step === "forgot" && (
        <form onSubmit={sendReset} className="flex flex-col gap-3">
          <p className="text-base text-muted">Enter your account&apos;s email and we&apos;ll send you a code.</p>
          {emailInput}
          <button type="submit" className={button} disabled={busy}>
            Send code
          </button>
          <button type="button" className={linkButton} onClick={() => go("login")}>
            Back to log in
          </button>
        </form>
      )}

      {step === "newPassword" && (
        <form onSubmit={savePassword} className="flex flex-col gap-3">
          {passwordInput("new-password", `New password (at least ${MIN_PASSWORD} characters)`)}
          <button type="submit" className={button} disabled={busy}>
            Save and log in
          </button>
        </form>
      )}

      {status && (
        <p role="status" className="text-base">
          {status}
        </p>
      )}
    </main>
    </>
  );
}
