import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CASHFREE_API_VERSION = "2025-01-01";
const CASHFREE_ORDERS_URL = "https://sandbox.cashfree.com/pg/orders";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

type CreateOrderBody = {
  mentor_id?: string;
  amount?: number;
  customer_name?: string;
  customer_email?: string;
  customer_phone?: string;
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

function roundMoney(value: number): number {
  return Math.round(value * 100) / 100;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return jsonResponse({ error: "Method not allowed" }, 405);

  try {
    const supabaseUrl = requiredEnv("SUPABASE_URL");
    const serviceRoleKey = requiredEnv("SUPABASE_SERVICE_ROLE_KEY");
    const cashfreeAppId = requiredEnv("CASHFREE_APP_ID");
    const cashfreeSecretKey = requiredEnv("CASHFREE_SECRET_KEY");

    const admin = createClient(supabaseUrl, serviceRoleKey, {
      auth: { persistSession: false, autoRefreshToken: false },
    });

    const body = (await req.json()) as CreateOrderBody;
    const mentorId = body.mentor_id?.trim();
    const amount = Number(body.amount);
    const customerName = body.customer_name?.trim();
    const customerEmail = body.customer_email?.trim();
    const customerPhone = body.customer_phone?.trim();

    if (!mentorId) return jsonResponse({ error: "mentor_id is required" }, 400);
    if (!Number.isFinite(amount) || amount <= 0) return jsonResponse({ error: "amount must be positive" }, 400);
    if (!customerName || !customerEmail || !customerPhone) {
      return jsonResponse({ error: "customer_name, customer_email, and customer_phone are required" }, 400);
    }

    const authHeader = req.headers.get("Authorization") ?? "";
    const token = authHeader.replace(/^Bearer\s+/i, "").trim();
    const { data: authUser } = token
      ? await admin.auth.getUser(token).catch(() => ({ data: { user: null } } as any))
      : { data: { user: null } };

    let subscriberId = authUser.user?.id as string | undefined;
    if (!subscriberId) {
      const { data: subscriberUser, error: subscriberError } = await admin
        .from("users")
        .select("id,email,is_active")
        .eq("email", customerEmail.toLowerCase())
        .eq("is_active", true)
        .maybeSingle();
      if (subscriberError) throw subscriberError;
      subscriberId = subscriberUser?.id;
    }

    if (!subscriberId) {
      return jsonResponse({ error: "Unable to resolve subscriber. Please sign in before subscribing." }, 401);
    }

    const { data: mentorProfile, error: mentorError } = await admin
      .from("profiles")
      .select("id,user_id,role,full_name,display_name,cashfree_vendor_id")
      .or(`id.eq.${mentorId},user_id.eq.${mentorId}`)
      .maybeSingle();

    if (mentorError) throw mentorError;
    if (!mentorProfile || mentorProfile.role !== "pro_trader") {
      return jsonResponse({ error: "Pro-Trader profile not found" }, 404);
    }

    const mentorUserId = mentorProfile.user_id ?? mentorProfile.id;
    const { data: proTraderProfile, error: proTraderError } = await admin
      .from("pro_trader_profiles")
      .select("cf_seller_id,monthly_subscription_price")
      .eq("user_id", mentorUserId)
      .maybeSingle();

    if (proTraderError) throw proTraderError;

    const vendorId = mentorProfile.cashfree_vendor_id || proTraderProfile?.cf_seller_id;
    if (!vendorId) {
      return jsonResponse({ error: "This Pro-Trader does not have a Cashfree vendor ID configured" }, 400);
    }

    const orderId = `TW_${crypto.randomUUID().replaceAll("-", "").slice(0, 24).toUpperCase()}`;
    const mentorAmount = roundMoney(amount * 0.9);
    const adminAmount = roundMoney(amount - mentorAmount);
    const frontendOrigin = Deno.env.get("FRONTEND_ORIGIN") || "http://localhost:5500";
    const returnUrl = `${frontendOrigin.replace(/\/$/, "")}/learner/pages/payment-return.html?order_id={order_id}`;
    const notifyUrl = `${supabaseUrl.replace(/\/$/, "")}/functions/v1/cashfree-webhook`;

    const cashfreePayload = {
      order_id: orderId,
      order_amount: roundMoney(amount),
      order_currency: "INR",
      customer_details: {
        customer_id: subscriberId,
        customer_name: customerName,
        customer_email: customerEmail,
        customer_phone: customerPhone,
      },
      order_meta: {
        return_url: returnUrl,
        notify_url: notifyUrl,
      },
      order_tags: {
        mentor_id: mentorUserId,
        subscriber_id: subscriberId,
        platform: "tradewise",
      },
      // Cashfree Easy Split: the unsplit balance is retained by the merchant/admin.
      order_splits: [
        {
          vendor_id: vendorId,
          amount: mentorAmount,
        },
      ],
    };

    const cashfreeResponse = await fetch(CASHFREE_ORDERS_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-version": CASHFREE_API_VERSION,
        "x-client-id": cashfreeAppId,
        "x-client-secret": cashfreeSecretKey,
      },
      body: JSON.stringify(cashfreePayload),
    });

    const cashfreeJson = await cashfreeResponse.json().catch(() => ({}));
    if (!cashfreeResponse.ok) {
      console.error("Cashfree create order failed", cashfreeResponse.status, cashfreeJson);
      return jsonResponse({ error: "Failed to create Cashfree order", details: cashfreeJson }, 502);
    }

    const { error: txError } = await admin.from("transactions").upsert({
      order_id: orderId,
      amount: roundMoney(amount),
      status: "PENDING",
      subscriber_id: subscriberId,
      mentor_id: mentorUserId,
      split_admin_amount: adminAmount,
      split_mentor_amount: mentorAmount,
      updated_at: new Date().toISOString(),
    }, { onConflict: "order_id" });

    if (txError) throw txError;

    return jsonResponse({
      order_id: orderId,
      payment_session_id: cashfreeJson.payment_session_id,
    });
  } catch (error) {
    console.error("create-order error", error);
    return jsonResponse({ error: "Unable to create payment order" }, 500);
  }
});

/*
Sandbox test details:
- Card: 4706131211212123, Expiry: 03/2028, CVV: 123, OTP: 111000
- UPI: testsuccess@gocash
- Net banking bank code: 3333
*/
