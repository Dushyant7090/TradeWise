import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CASHFREE_API_VERSION = "2025-01-01";
const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

function requiredEnv(name: string): string {
  const value = Deno.env.get(name);
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
}

function isPaid(order: any): boolean {
  return String(order?.order_status || "").toUpperCase() === "PAID";
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (!["GET", "POST"].includes(req.method)) return jsonResponse({ error: "Method not allowed" }, 405);

  try {
    const url = new URL(req.url);
    let orderId = url.searchParams.get("order_id") || "";
    if (!orderId && req.method === "POST") {
      const body = await req.json().catch(() => ({}));
      orderId = body.order_id || "";
    }
    if (!orderId) return jsonResponse({ error: "order_id is required" }, 400);

    const admin = createClient(requiredEnv("SUPABASE_URL"), requiredEnv("SUPABASE_SERVICE_ROLE_KEY"), {
      auth: { persistSession: false, autoRefreshToken: false },
    });

    const { data: tx, error: txError } = await admin
      .from("transactions")
      .select("*")
      .eq("order_id", orderId)
      .maybeSingle();

    if (txError) throw txError;
    if (!tx) return jsonResponse({ error: "Payment order not found" }, 404);

    const cashfreeResponse = await fetch(`https://sandbox.cashfree.com/pg/orders/${encodeURIComponent(orderId)}`, {
      headers: {
        "x-api-version": CASHFREE_API_VERSION,
        "x-client-id": requiredEnv("CASHFREE_APP_ID"),
        "x-client-secret": requiredEnv("CASHFREE_SECRET_KEY"),
      },
    });

    const cashfreeOrder = await cashfreeResponse.json().catch(() => ({}));
    if (!cashfreeResponse.ok) {
      return jsonResponse({ error: "Unable to verify order", details: cashfreeOrder }, 502);
    }

    let mentorName = "this Pro-Trader";
    const { data: mentorProfile } = await admin
      .from("profiles")
      .select("full_name,display_name")
      .or(`id.eq.${tx.mentor_id},user_id.eq.${tx.mentor_id}`)
      .maybeSingle();
    if (mentorProfile) mentorName = mentorProfile.full_name || mentorProfile.display_name || mentorName;

    if (isPaid(cashfreeOrder)) {
      const now = new Date();
      const end = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);

      await admin.from("transactions").update({
        status: "SUCCESS",
        updated_at: now.toISOString(),
      }).eq("order_id", orderId);

      await admin.from("subscriptions").upsert({
        subscriber_id: tx.subscriber_id,
        trader_id: tx.mentor_id,
        mentor_id: tx.mentor_id,
        status: "active",
        started_at: now.toISOString(),
        ends_at: end.toISOString(),
        start_date: now.toISOString(),
        end_date: end.toISOString(),
        amount_paid: tx.amount,
        cashfree_order_id: orderId,
      }, { onConflict: "cashfree_order_id", ignoreDuplicates: true });
    }

    return jsonResponse({
      order_id: orderId,
      status: isPaid(cashfreeOrder) ? "SUCCESS" : "PENDING",
      cashfree_status: cashfreeOrder.order_status,
      mentor_name: mentorName,
    });
  } catch (error) {
    console.error("verify-payment error", error);
    return jsonResponse({ error: "Unable to verify payment" }, 500);
  }
});
