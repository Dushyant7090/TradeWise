-- Allow zero RRR so trades with stop-loss equal to entry can be stored.
ALTER TABLE public.trades
  DROP CONSTRAINT IF EXISTS chk_trades_rrr_positive;

ALTER TABLE public.trades
  DROP CONSTRAINT IF EXISTS chk_trades_rrr_non_negative;

ALTER TABLE public.trades
  ADD CONSTRAINT chk_trades_rrr_non_negative CHECK (rrr >= 0);
