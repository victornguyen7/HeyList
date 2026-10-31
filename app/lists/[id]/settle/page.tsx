"use client";

import { SettleUp, useSplit } from "../../../split";
import { useList } from "../list-context";

// Settle up: the fewest payments that even out what everyone paid (Figma "5 · List — Settle up").
export default function SettlePage() {
  const { list, me } = useList();
  const split = useSplit(list);

  if (!split) return <p className="text-base text-muted-on-bg">Working it out…</p>;
  return (
    <div className="pt-[30px] lg:mx-auto lg:w-full lg:max-w-[560px]">
      <SettleUp list={list} split={split} me={me} />
    </div>
  );
}
