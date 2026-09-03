/**
 * Authenticated form-image byte stream (ADR-0042 / FR-P2-15).
 *
 * Dedicated route (G1): image bytes are not a JSON dispatcher payload.
 * Auth via requireEngineClaim; missing asset ⇒ 404, never a broken image.
 */

import { NextRequest } from "next/server";
import { enginePorts, serverPortBag } from "@/lib/bff/server_composition";
import { notFound, requireEngineClaim } from "@/lib/bff/engine_guard";

export const dynamic = "force-dynamic";

export async function GET(
  _req: NextRequest,
  ctx: { params: Promise<{ formId: string; key: string }> },
): Promise<Response> {
  const bag = serverPortBag();
  const claimOrRes = await requireEngineClaim(() =>
    bag.authProvider.getSession(),
  );
  if (claimOrRes instanceof Response) return claimOrRes;

  const store = enginePorts().formAssetStore;
  if (store == null) return notFound();

  const { formId, key } = await ctx.params;
  if (!formId || !key) return notFound();

  const bytes = await store.getImage({
    store: "form-image",
    form_id: formId,
    key: decodeURIComponent(key),
  });
  // G9: null = missing key (FormAssetStore contract) — 404, not empty bytes.
  if (bytes == null) return notFound();

  return new Response(Buffer.from(bytes), {
    status: 200,
    headers: {
      "content-type": "image/png",
      "cache-control": "private",
    },
  });
}
