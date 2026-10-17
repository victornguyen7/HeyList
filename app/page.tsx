"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Starter } from "./starter";

export default function Home() {
  const router = useRouter();
  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-6 px-4 py-10">
      <div className="flex items-baseline justify-between">
        <h1 className="text-4xl font-bold">HeyList</h1>
        <Link href="/history" className="text-lg underline underline-offset-4">
          History
        </Link>
      </div>
      <Starter onCreated={(created) => router.push(`/lists/${created.id}`)} />
    </main>
  );
}
