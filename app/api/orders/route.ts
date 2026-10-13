import { createOrder, PayPalError } from "@/lib/paypal";
import { totalCents } from "@/lib/sample-list";

export async function POST(request: Request) {
  let itemIds: string[];
  try {
    ({ itemIds } = await request.json());
    totalCents(itemIds);
  } catch {
    return Response.json({ error: "INVALID_ITEMS" }, { status: 400 });
  }

  try {
    return Response.json({ orderId: await createOrder(itemIds) });
  } catch (error) {
    if (!(error instanceof PayPalError)) console.error(error);
    return Response.json({ error: "PAYPAL_ERROR" }, { status: 502 });
  }
}
