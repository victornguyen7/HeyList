import { captureOrder, PayPalError } from "@/lib/paypal";

export async function POST(
  _request: Request,
  ctx: RouteContext<"/api/orders/[id]/capture">,
) {
  const { id } = await ctx.params;
  if (!/^[A-Z0-9]{1,36}$/.test(id)) {
    return Response.json({ error: "INVALID_ORDER_ID" }, { status: 400 });
  }

  try {
    return Response.json(await captureOrder(id));
  } catch (error) {
    if (error instanceof PayPalError && error.issue === "INSTRUMENT_DECLINED") {
      return Response.json({ error: "INSTRUMENT_DECLINED" }, { status: 422 });
    }
    if (!(error instanceof PayPalError)) console.error(error);
    return Response.json({ error: "PAYPAL_ERROR" }, { status: 502 });
  }
}
