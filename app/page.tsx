import { Suspense } from "react";
import { Checklist } from "./checklist";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col px-4 py-10">
      <Suspense>
        <Checklist />
      </Suspense>
    </main>
  );
}
