"""alpaca-options-saas backend — a thin multi-tenant API/worker around the
`alpaca_options_agent` package. The package stays the single source of truth
for strategy / risk / execution logic; this layer only adds auth, per-user
config, persistence, and Telegram/WhatsApp notifications.
"""
