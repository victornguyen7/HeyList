import { Suspense } from "react";
import { ListProvider } from "./list-context";

export default function ListLayout({ children }: LayoutProps<"/lists/[id]">) {
  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col px-4 py-10">
      <Suspense fallback={<p className="text-lg">Loading…</p>}>
        <ListProvider>{children}</ListProvider>
      </Suspense>
    </main>
  );
}
