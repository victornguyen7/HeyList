import type { RealtimeChannel } from "@supabase/supabase-js";
import { supabase } from "./auth";

// Live list updates (decision 59): one Supabase Realtime broadcast channel per list. A page that changed the list
// sends a "changed" ping with no data in it, and every other open page of that list reloads it through the API, so
// link-shared lists stay unreadable to the database's anonymous role.
// A channel stays open for the rest of the visit once a list is opened: Supabase reuses a channel by topic and
// removes one asynchronously, so closing it on unmount would hand Strict Mode's second mount a channel being torn down.
const channels = new Map<string, RealtimeChannel>();
const listeners = new Map<string, Set<() => void>>();

/** Calls `onChange` when someone else changes the list. Returns the function that stops it. */
export function onListChanged(listId: string, onChange: () => void): () => void {
  let set = listeners.get(listId);
  if (!set) {
    const callbacks = new Set<() => void>();
    set = callbacks;
    listeners.set(listId, callbacks);
    channels.set(
      listId,
      supabase
        .channel(`list:${listId}`)
        .on("broadcast", { event: "changed" }, () => callbacks.forEach((callback) => callback()))
        .subscribe(),
    );
  }
  set.add(onChange);
  return () => void set.delete(onChange);
}

/** Tells the other open pages of the list to reload it. A missed ping heals when their tab is shown again. */
export function listChanged(listId: string) {
  void channels.get(listId)?.send({ type: "broadcast", event: "changed", payload: {} });
}
