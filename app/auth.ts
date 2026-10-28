import { createClient, type Session } from "@supabase/supabase-js";
import { useEffect, useState } from "react";

// Email login (Supabase Auth, magic link). Optional: guests still join a list by name (decision 6).
// The link lands back on the page that asked for it, and the client reads the session from the URL.
export const supabase = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!);

/** The logged-in session, or null for a guest (and until it has been read). */
export function useSession(): Session | null {
  const [session, setSession] = useState<Session | null>(null);
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, next) => setSession(next));
    return () => data.subscription.unsubscribe();
  }, []);
  return session;
}

/** The name saved on the account, set the first time a logged-in person joins a list. */
export const accountName = (session: Session | null): string | undefined => session?.user.user_metadata.name;
