# RESULTS.md — evidence ledger (newest first)

Economic acceptance requires continuous common capital, all broker costs, funded completed weekly HARD21 and marked-equity drawdown. These figures are *historical development* observations, not independent confirmation, a broker P&L statement, or a qualified cBot.

| As of | Study | Source / original | Central modeled NET EUR | Adverse NET EUR | Best complete week | HARD21 qualified weeks | Sampled DD max | Decision |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 2026-11-23 | New general-state C# | Actions #45111043597 | NOT_AVAILABLE | NOT_AVAILABLE | NOT_AVAILABLE | NOT_AVAILABLE | NOT_AVAILABLE | IN_PROGRESS at P0 inventory; do not invent results |
| 2026-11-22 | VALUE_CONTEXT | Actions #45032546544 / artifact #14763540968 | -1.963785 | 0 (no adverse trades) | 17 | 0/11 | 0.654595% central sampled only | FAIL NET and HARD21 |
| 2026-11-22 | VALUE_FIRST comparator | Same immutable original | -88.020427 | -89.002580 | 220 central | 6/11 central, 5/11 adverse | 29.973028% central sampled only | FAIL NET and HARD21; unknown financing/path |
| 2026-11-22 | CASH comparator | Same immutable original | 0 | 0 | 0 | 0/11 | 0% | BASELINE ONLY, not tradable HARD21 |

Source document (no reexecution): original public aggregate `economic.json` SHA256 `31eeee228e017fb6d9b29d22430ec4a5a1ae2dc66f485aae96cef46c9e05b858` verified against original `receipt.json/OutputSha256`. Source evaluation period 2026-08-10 to 2026-10-26 UTC, 11 complete ISO weeks. Historical financial terms are partly conditional; maximal *continuous* intrabar DD, full broker parity, source-confirmed fills and independent results are NOT_AVAILABLE. Other section-18 diagnostics not proven by this source are NOT_AVAILABLE rather than 0.

Every new method must be preregistered, compared with matched CASH/trivial/random after spread x1/x1.5/x2, and reported under frozen split in `DECISIONS.md`. Nothing here authorizes LIVE/DEMO orders or Cloud.
