/**
 * realtime.js — Supabase Realtime subscriptions for live updates
 */

// Supabase Realtime client (loaded via CDN in HTML)
let supabase = null;
const subscriptions = {};

const Realtime = {
  /**
   * Initialize Supabase client for realtime
   * @param {string} url - Supabase project URL
   * @param {string} anonKey - Supabase anon key
   */
  init(url, anonKey) {
    if (!url && !anonKey) {
      return;
    }
    if (!url || !anonKey || !url.startsWith('https://') || anonKey.length < 20) {
      console.warn('Realtime: Valid Supabase credentials required. Realtime disabled.');
      return;
    }
    try {
      supabase = window.supabase?.createClient(url, anonKey);
      if (supabase) console.log('Realtime: Supabase client initialized.');
    } catch (e) {
      console.warn('Realtime: Failed to initialize Supabase client.', e);
    }
  },

  _isReady() {
    return !!supabase;
  },

  /**
   * Subscribe to trade updates for the current pro-trader
   * @param {string} traderId - UUID of the pro-trader user
   * @param {Function} onInsert - callback(payload)
   * @param {Function} onUpdate - callback(payload)
   */
  subscribeToTrades(traderId, { onInsert, onUpdate } = {}) {
    if (!this._isReady()) return;

    const channel = supabase
      .channel(`trades:${traderId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'trades',
          filter: `pro_trader_id=eq.${traderId}`,
        },
        (payload) => onInsert && onInsert(payload)
      )
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'trades',
          filter: `pro_trader_id=eq.${traderId}`,
        },
        (payload) => onUpdate && onUpdate(payload)
      )
      .subscribe((status) => {
        if (status === 'SUBSCRIBED') {
          console.log(`Realtime: Subscribed to trades for trader ${traderId}`);
        }
      });

    subscriptions[`trades:${traderId}`] = channel;
    return channel;
  },

  /**
   * Subscribe to notifications for the current user
   * @param {string} userId
   * @param {Function} onNew - callback(notification)
   */
  subscribeToNotifications(userId, onNew) {
    if (!this._isReady()) return;

    const channel = supabase
      .channel(`notifications:${userId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'notifications',
          filter: `user_id=eq.${userId}`,
        },
        (payload) => {
          if (onNew) onNew(payload.new);
        }
      )
      .subscribe();

    subscriptions[`notifications:${userId}`] = channel;
    return channel;
  },

  /**
   * Subscribe to payout status updates
   * @param {string} userId
   * @param {Function} onUpdate - callback(payout)
   */
  subscribeToPayouts(userId, onUpdate) {
    if (!this._isReady()) return;

    const channel = supabase
      .channel(`payouts:${userId}`)
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'payouts',
          filter: `user_id=eq.${userId}`,
        },
        (payload) => {
          if (onUpdate) onUpdate(payload.new);
        }
      )
      .subscribe();

    subscriptions[`payouts:${userId}`] = channel;
    return channel;
  },

  /**
   * Subscribe to trade comments (realtime updates)
   * @param {string} tradeId
   * @param {Function} onNew - callback(comment)
   */
  subscribeToComments(tradeId, onNew) {
    if (!this._isReady()) return;

    const channel = supabase
      .channel(`comments:${tradeId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'comments',
          filter: `trade_id=eq.${tradeId}`,
        },
        (payload) => {
          if (onNew) onNew(payload.new);
        }
      )
      .subscribe();

    subscriptions[`comments:${tradeId}`] = channel;
    return channel;
  },

  /**
   * Subscribe to all new trades (for learner feed)
   * @param {Object} callbacks - { onInsert }
   */
  subscribeToNewTrades({ onInsert } = {}) {
    if (!this._isReady()) return;

    const channel = supabase
      .channel('trades:all_new')
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'trades',
        },
        (payload) => onInsert && onInsert(payload)
      )
      .subscribe((status) => {
        if (status === 'SUBSCRIBED') {
          console.log('Realtime: Subscribed to all new trades');
        }
      });

    subscriptions['trades:all_new'] = channel;
    return channel;
  },

  /**
   * Subscribe to status changes on specific trades (for learners)
   * Fires when a trade they unlocked gets closed (target_hit / sl_hit)
   * @param {string[]} tradeIds - array of trade UUIDs
   * @param {Function} onUpdate - callback(updatedTrade)
   */
  subscribeToTradeStatus(tradeIds, onUpdate) {
    if (!this._isReady() || !tradeIds?.length) return;

    // Subscribe to first 50 trades to avoid channel overhead
    const ids = tradeIds.slice(0, 50);
    const channel = supabase
      .channel('trades:status_watch')
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'trades',
        },
        (payload) => {
          if (ids.includes(payload.new?.id) && onUpdate) {
            onUpdate(payload.new);
          }
        }
      )
      .subscribe();

    subscriptions['trades:status_watch'] = channel;
    return channel;
  },

  /**
   * Unsubscribe a specific channel
   */
  unsubscribe(key) {
    if (subscriptions[key] && supabase) {
      supabase.removeChannel(subscriptions[key]);
      delete subscriptions[key];
    }
  },

  /**
   * Unsubscribe all channels (call on page leave)
   */
  unsubscribeAll() {
    if (!supabase) return;
    Object.keys(subscriptions).forEach(key => {
      supabase.removeChannel(subscriptions[key]);
      delete subscriptions[key];
    });
  },
};

export default Realtime;
