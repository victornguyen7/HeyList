import { connection } from "next/server";
import { Suspense } from "react";
import ListView from "./list-view";

// Renders on every request, so it has to sit inside <Suspense> (cacheComponents is on).
async function Loaded({ listId }: { listId: string }) {
  // The PayPal client ID comes from the running server, not the build machine (decision 45).
  await connection();
  return <ListView listId={listId} clientId={process.env.PAYPAL_CLIENT_ID ?? ""} />;
}

export default function ListPage({ params }: PageProps<"/l/[id]">) {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-5 p-5">
      <Suspense fallback={<p className="text-xl">Loading the list…</p>}>
        {params.then(({ id }) => (
          <Loaded listId={id} />
        ))}
      </Suspense>
    </main>
  );
}
