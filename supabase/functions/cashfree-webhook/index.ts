import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type, x-webhook-signature, x-webhook-timestamp",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function ok(body: Record<string, unknown> = { status: "ok" }) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

function requiredEnv(name: string): string {
  const value = Deno.env.get(name);
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
}

function bytesToHex(bytes: ArrayBuffer): string {
  return [...new Uint8Array(bytes)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function bytesToBase64(bytes: ArrayBuffer): string {
  let binary = "";
  for (const byte of new Uint8Array(bytes)) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function timingSafeEqual(a: string, b: string): boolean {
  const encoder = new TextEncoder();
  const aa = encoder.encode(a);
  const bb = encoder.encode(b);
  if (aa.length !== bb.length) return false;
  let out = 0;
  for (let i = 0; i < aa.length; i++) out |= aa[i] ^ bb[i];
  return out === 0;
}

async function verifyCashfreeSignature(rawBody: string, signature: string, timestamp: string): Promise<boolean> {
  const secret = Deno.env.get("CASHFREE_WEBHOOK_SECRET") ?? "";
  if (!secret) return true;
  if (!signature || !timestamp) return false;

  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const digest = await crypto.subtle.sign("HMAC", key, encoder.encode(`${timestamp}${rawBody}`));
  const expectedHex = bytesToHex(digest);
  const expectedBase64 = bytesToBase64(digest);

  return timingSafeEqual(signature, expectedHex) || timingSafeEqual(signature, expectedBase64);
}

function isSuccessEvent(payload: any): boolean {
  const eventName = String(payload?.type || payload?.event || payload?.event_type || "").toUpperCase();
  const paymentStatus = String(payload?.data?.payment?.payment_status || "").toUpperCase();
  const orderStatus = String(payload?.data?.order?.order_status || "").toUpperCase();
  return eventName.includes("PAYMENT_SUCCESS") || paymentStatus === "SUCCESS" || orderStatus === "PAID";
}

function isFailureEvent(payload: any): boolean {
  const eventName = String(payload?.type || payload?.event || payload?.event_type || "").toUpperCase();
  const paymentStatus = String(payload?.data?.payment?.payment_status || "").toUpperCase();
  const orderStatus = String(payload?.data?.order?.order_status || "").toUpperCase();
  return eventName.includes("PAYMENT_FAILED") || ["FAILED", "USER_DROPPED", "CANCELLED"].includes(paymentStatus) || orderStatus === "EXPIRED";
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return ok({ status: "ignored", reason: "method" });

  try {
    const rawBody = await req.text();
    const signature = req.headers.get("x-webhook-signature") ?? "";
    const timestamp = req.headers.get("x-webhook-timestamp") ?? "";
    const isValid = await verifyCashfreeSignature(rawBody, signature, timestamp);

    if (!isValid) {
      console.warn("Cashfree webhook signature verification failed");
      return ok({ status: "ignored", reason: "invalid_signature" });
    }

    const payload = JSON.parse(rawBody);
    const order = payload?.data?.order ?? {};
    const payment = payload?.data?.payment ?? {};
    const orderId = order.order_id ?? payload?.order_id;
    const paymentId = String(payment.cf_payment_id ?? payment.payment_id ?? "");

    if (!orderId) return ok({ status: "ignored", reason: "missing_order_id" });

    const admin = createClient(requiredEnv("SUPABASE_URL"), requiredEnv("SUPABASE_SERVICE_ROLE_KEY"), {
      auth: { persistSession: false, autoRefreshToken: false },
    });

    const { data: existingTx, error: txLookupError } = await admin
      .from("transactions")
      .select("*")
      .eq("order_id", orderId)
      .maybeSingle();

    if (txLookupError) throw txLookupError;
    if (!existingTx) return ok({ status: "ignored", reason: "unknown_order" });

    if (isSuccessEvent(payload)) {
      const now = new Date();
      const end = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);

      const { error: txUpdateError } = await admin.from("transactions").upsert({
        order_id: orderId,
        payment_id: paymentId,
        amount: existingTx.amount,
        status: "SUCCESS",
        subscriber_id: existingTx.subscriber_id,
        mentor_id: existingTx.mentor_id,
        split_admin_amount: existingTx.split_admin_amount,
        split_mentor_amount: existingTx.split_mentor_amount,
        raw_event: payload,
        updated_at: now.toISOString(),
      }, { onConflict: "order_id" });
      if (txUpdateError) throw txUpdateError;

      const { error: subError } = await admin.from("subscriptions").upsert({
        subscriber_id: existingTx.subscriber_id,
        trader_id: existingTx.mentor_id,
        mentor_id: existingTx.mentor_id,
        status: "active",
        started_at: now.toISOString(),
        ends_at: end.toISOString(),
        start_date: now.toISOString(),
        end_date: end.toISOString(),
        amount_paid: existingTx.amount,
        cashfree_order_id: orderId,
      }, { onConflict: "cashfree_order_id", ignoreDuplicates: true });
      if (subError) throw subError;

      return ok({ status: "processed" });
    }

    if (isFailureEvent(payload)) {
      await admin.from("transactions").update({
        payment_id: paymentId || existingTx.payment_id,
        status: "FAILED",
        raw_event: payload,
        updated_at: new Date().toISOString(),
      }).eq("order_id", orderId);
      console.info("Cashfree payment failed", orderId);
    }

    return ok();
  } catch (error) {
    console.error("cashfree-webhook error", error);
    return ok({ status: "error_logged" });
  }
});
