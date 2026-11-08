# PayPal architecture

PayPal Checkout is an external Sandbox buyer-funded source. A completed PayPal order updates `paypal_orders` and the linked payment request, but creates no internal reservation, no wallet debit, and no journal entry. Wallet-funded payments continue through the existing reservation, demo provider, and journal path.

`app.paypal` owns OAuth caching, Decimal currency representation, Orders v2 calls, local mapping, capture verification, and webhook processing. INR stays canonical in the application. Because PayPal's published REST currency list does not include INR, the default Sandbox order is USD using the labelled test rate `PAYPAL_DEMO_INR_PER_USD=84`; this is not FX or a ledger conversion.
