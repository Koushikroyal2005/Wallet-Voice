# Product flows

The simulator emits Railway (4 minutes), Movie (2 hours), or unverified Electronics (flexible) requests. The server calculates priority from the stored UTC expiry: under 15 minutes is urgent, 15 minutes through 3 hours is due soon, otherwise flexible.

AutoPay must be enabled for automatic batch eligibility. Time-sensitive-only further excludes flexible requests. Manual **Pay now** remains a visible, user-controlled demo action.
