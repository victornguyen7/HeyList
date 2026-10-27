import { Suspense } from "react";
import { ListProvider } from "./list-context";

// The list is fetched in the browser (ListProvider), so its pages render nothing on the server and can't
// navigate instantly; opt them out of instant-navigation validation instead of reporting dropped segments.
export const instant = false;

export default function ListLayout({ children }: LayoutProps<"/lists/[id]">) {
  return (
    <main className="flex flex-1 flex-col">
      <Suspense fallback={<p className="text-base text-muted">Loading…</p>}>
        <ListProvider>{children}</ListProvider>
      </Suspense>
    </main>
  );
}
