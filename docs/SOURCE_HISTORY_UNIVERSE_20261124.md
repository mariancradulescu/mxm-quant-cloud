# OWNER SOURCE-ONLY history and universe, 2026-11-24

Distinct from completed P05 point run #45390363694. No original economic study or artifact is changed or rerun.

Official Spotware references: https://help.ctrader.com/open-api/messages/#protooadeallistreq ; https://help.ctrader.com/open-api/model-messages/#protooaclosepositiondetail ; https://help.ctrader.com/open-api/messages/#protooasymbolbyidreq ; https://help.ctrader.com/open-api/messages/#protooagettrendbarsreq ; https://help.ctrader.com/open-api/ .

- Query weekly closed/in-flight account execution history from 2025-11-17 UTC to 2026-11-24 UTC exclusive, splitting pages with hasMore (160 deal requests maximum). Actual account swap on realized closes is not a historical market tariff and cannot be transferred to hypothetical positions.
- Query all returned nonarchived symbol contracts in 50-ID batches; retain missing and failed states. Visibility is not eligibility. Full returned roster is inventory, not a trading whitelist.
- First bounded timeframe tranche: 16 category-round-robin visible symbols, independent of prior P&L. M1/M5/M15/M30/H1/H4/D1 and a fixed recent seven-day window, minimum-volume margin estimate if terms allow. Other symbol/timeframe cells remain NECOLECTAT. No seven-day sample certifies long-term coverage. Subsequent tranches must cover outstanding cells rather than create permanent exclusions.
- Keep raw request/response protobuf, timestamps, errors (raw protected), immutable encrypted original, receipt, protected independent reconstruction. No token/authentication packets in artifacts. Public receipt does not disclose raw account deals, identifiers or amounts of actual past swap. Never infer missing moneyDigits or historical tariff effective intervals.
- At most 520 attempted requests, bounded wall clock, conservative serial pacing below official historical 5/sec. Separate old guard and transport unchanged; only this scoped adapter adds exact historical deal reads at final wire boundary.
- No order mutations, Cloud, economic evaluation, or usable funding offer. A missing response or empty response is not confirmed unavailable.
