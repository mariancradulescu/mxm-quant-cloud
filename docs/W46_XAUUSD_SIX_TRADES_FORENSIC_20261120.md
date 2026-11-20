# Six original XAUUSD adverse RANK settlements — forensic, no intervention

Source ORIGINAL Actions #44735700353, artifact #14627239908, sha256 `economic.json` `d77603ad36b989b4aa2c3a53dfa3c4323401c4553cb9ecc43793f541f17c45c9`. Times UTC, all **modeled** on later source quotes, not broker-confirmed executions. Family is `RANGE_EDGE_REJECTION` for all six. Entry quantity 1 (original minimum modeled volume), `OPEN_FILL` margin per unit **161.745 EUR** on captured contract snapshot; not authenticated historical margin. All six original M15 theses have an admission and fill close witness, and none of their original trip records marks `CrossedUnknownHistory=true`.

| Close (UTC, 2026) | Direction | Gross € | Costs € | NET € | Ex-ante mean forecast € | Planned entry risk € | Stress at fill € | Modeled exit |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 09 Nov 11:12:45 | SHORT | −2.108150 | 0.357330 | **−2.465480** | −0.849878 | 2.6089 | 4.8886 | observed thesis invalidation |
| 10 Nov 20:39:15 | SHORT | +4.962290 | 0.358286 | **+4.604004** | −0.195815 | 2.9288 | 5.7233 | observed target |
| 11 Nov 10:48:45 | LONG | +3.975876 | 0.350026 | **+3.625850** | −0.630594 | 1.9928 | 5.1009 | observed target |
| 12 Nov 11:16:15 | SHORT | +5.624561 | 0.351529 | **+5.273031** | −0.277087 | 1.5230 | 4.2837 | observed target |
| 13 Nov 10:17:45 | SHORT | +2.352068 | 0.280435 | **+2.071634** | −0.641135 | 2.4784 | 5.7203 | observed target |
| 13 Nov 19:31:45 | LONG | −1.763852 | 0.331006 | **−2.094858** | −1.736107 | 1.9770 | 4.5676 | observed thesis invalidation |
| **Total** | | | **2.028612** | **+11.014180** | | | | |

Aggregate original costs: commission **€0.377956**, spread **€0.553147**, modeled slippage **€1.097499**, conversion **€0.000011**. These amount to **€2.028612**. Both losing XAU trades happened to have negative forecasts, but **all four positive ones also had negative forecasts**; this does not establish positive economic ranking skill.

The 10 Nov SHORT is absent from FIRST and POOLED original model books and present in RANK and REJECTION. It explains €4.604004 of the €4.687875 RANK-versus-FIRST **accounting** delta. The largest profit (12 Nov €5.273031) is present in FIRST too and so does **not** explain the increment. Six XAU positions plus the remaining 80 contribute €11.014180 − €5.047588 = **€5.966592** adverse RANK NET. Portfolio-wide margin, simultaneous exposures, later allocation, costs and unknown floating equity require a complete funded replay for any actual exclusion counterfactual.

**Status:** original arithmetic VERIFIED; trade fills, historical broker margin and tariff certification, prospective edge, and economic ablation NOT VERIFIED. No W46 retuning, no broker calls, no orders, no Cloud activation.
