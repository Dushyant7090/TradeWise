/**
 * realtime.js — Supabase Realtime subscriptions for TradeWise Learner
 */

let supabase = null;
const subscriptions = {};

/** Minimum length for a valid Supabase anonymous key */
const MIN_ANON_KEY_LENGTH = 20;

const Realtime = {
  /**
   * Initialize Supabase client for realtime
   */
  init(url, anonKey) {
    if (!url || !anonKey || !url.startsWith('https://') || anonKey.length < MIN_ANON_KEY_LENGTH) {
      console.warn('Realtime: Valid Supabase credentials required. Realtime disabled.');
      return;
    }
    try {
      supabase = window.supabase?.createClient(url, anonKey);
      if (supabase) console.log('Realtime: Supabase client initialized for learner.');
    } catch (e) {
      console.warn('Realtime: Failed to initialize Supabase client.', e);
    }
  },

  _isReady() {
    return !!supabase;
  },

  /**
   * Subscribe to new trades in the feed (all active trades)
   */
  subscribeToNewTrades({ onInsert } = {}) {
    if (!this._isReady()) return;
    const key = 'feed:trades';
    const channel = supabase
      .channel(key)
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'trades' },
        (payload) => onInsert && onInsert(payload.new))
      .subscribe((status) => {
        if (status === 'SUBSCRIBED') console.log('Realtime: Subscribed to feed trades');
      });
    subscriptions[key] = channel;
    return channel;
  },

  /**
   * Subscribe to real-time status updates for a specific trade
   */
  subscribeToTradeUpdates(tradeId, { onUpdate } = {}) {
    if (!this._isReady()) return;
    const key = `trade:${tradeId}`;
    const channel = supabase
      .channel(key)
      .on('postgres_changes',
        { event: 'UPDATE', schema: 'public', table: 'trades', filter: `id=eq.${tradeId}` },
        (payload) => onUpdate && onUpdate(payload.new))
      .subscribe();
    subscriptions[key] = channel;
    return channel;
  },

  /**
   * Subscribe to learner notifications
   */
  subscribeToNotifications(learnerId, { onInsert } = {}) {
    if (!this._isReady()) return;
    const key = `learner_notifications:${learnerId}`;
    const channel = supabase
      .channel(key)
      .on('postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'learner_notifications', filter: `learner_id=eq.${learnerId}` },
        (payload) => onInsert && onInsert(payload.new))
      .subscribe();
    subscriptions[key] = channel;
    return channel;
  },

  /**
   * Subscribe to comments on a trade
   */
  subscribeToComments(tradeId, { onInsert, onUpdate, onDelete } = {}) {
    if (!this._isReady()) return;
    const key = `comments:${tradeId}`;
    const channel = supabase
      .channel(key)
      .on('postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'comments', filter: `trade_id=eq.${tradeId}` },
        (payload) => onInsert && onInsert(payload.new))
      .on('postgres_changes',
        { event: 'UPDATE', schema: 'public', table: 'comments', filter: `trade_id=eq.${tradeId}` },
        (payload) => onUpdate && onUpdate(payload.new))
      .on('postgres_changes',
        { event: 'DELETE', schema: 'public', table: 'comments', filter: `trade_id=eq.${tradeId}` },
        (payload) => onDelete && onDelete(payload.old))
      .subscribe();
    subscriptions[key] = channel;
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
