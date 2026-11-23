# P0.5 — Test financiar rapid HARD21: fricțiune pentru 21 tranzacții (23.11.2026)

**Status:** calcul aritmetic reproductibil asupra unor date autentice DEJA EXPLOSE; niciun nou broker request sau backtest, nicio promisiune de profit, nicio excludere definitivă.

Sursă: `docs/SYSTEM_ECONOMIC_FEASIBILITY.json`, SHA blob GitHub `697e853f6dbded9296f0a753bf5613ba9e361cb3` (original istoric, nu contract actual). Date sursă: `costContextRows[].baseRoundTripFrictionEnvelopeEur`, fricțiune de referință parțială pentru volumul minim, raportată deja pentru 12 instrumente. Aceasta **NU este costul all-in complet**: spread din eșantion istoric, comision, conversie, swap, slippage și lichiditate nu sunt toate certificate sincron pe fiecare semnal.

**Calcul:** pentru 21 tranzacții complete separate la volumul minim al aceluiași instrument, scenarii ipotetice `21 × baseRoundTripFrictionEnvelopeEur × k`, k∈{1, 1.5, 2}. Nu se presupune o strategie, direcție, oportunitate, preț executabil, capital reînnoit sau folosirea tuturor acestor tranzacții în aceeași zi. Pentru câștig NET pozitiv, P&L brut trebuie să depășească fricțiunea reală, care poate diferi semnificativ de proxy.

| Instrument | Marjă min. observată EUR | 21×proxy cost x1 EUR | 21×proxy x1,5 EUR | 21×proxy x2 EUR | x2 ca % din capital 300 EUR |
| --- | ---: | ---: | ---: | ---: | ---: |
| EURUSD | 33.33 | 2.18 | 3.28 | 4.37 | 1.46% |
| AUDUSD | 31.13 | 2.34 | 3.51 | 4.68 | 1.56% |
| USDCAD | 29.79 | 2.70 | 4.05 | 5.40 | 1.80% |
| US500 | 33.89 | 2.74 | 4.11 | 5.48 | 1.83% |
| USDJPY | 29.79 | 2.86 | 4.29 | 5.72 | 1.91% |
| GBPUSD | 39.96 | 3.74 | 5.61 | 7.48 | 2.49% |
| AUS200 | 27.50 | 7.24 | 10.86 | 14.48 | 4.83% |
| NAS100 | 126.50 | 9.13 | 13.69 | 18.25 | 6.08% |
| UK100 | 63.50 | 9.53 | 14.29 | 19.05 | 6.35% |
| GER40 | 129.17 | 13.07 | 19.60 | 26.14 | 8.71% |
| JPN225 | 177.95 | 26.86 | 40.29 | 53.72 | 17.91% |
| XAUUSD | 175.58 | 31.26 | 46.89 | 62.52 | 20.84% |

## Interpretare conservatoare
- La EURUSD, 21 runde la un volum minim ar avea proxy x2 de 4.37 EUR/săptămână. La XAUUSD proxy-ul x2 este 62.52 EUR/săptămână. Nu sunt pierderi sau profituri observate, ci condiții preliminare de recuperare a costului modelat.
- Profitul NET, tranzacțiile reale finanțabile, HARD21 în fiecare săptămână eligibilă și DD marcat la piață rămân **NEDEMONSTRATE**. Costul modelat pozitiv nu este semnal predictiv, iar marja punctuală sub 300 EUR nu validează o tranzacție.
- Instrumentele din clasele crypto, energie și acțiuni nu apar în această sursă de 12 și **nu sunt excluse**: se investighează separat cu întreaga listă de 5.339 simboluri de cont și eșantionul multi-clasă de 18, înainte de eventuală eliminare pe criterii verificabile.
- Matricea M15/M30/H1/H4/D1 și intervalele de cost și mișcare autentice nu sunt complete, iar sursa permite doar comparația parțială H1. **P0: DESCHIS. P0.5: NECONCLUDENT.**
- Experimentele istorice deja expuse rămân exclusiv descoperire (A). Niciun retuning pe perioada B sau C și nicio relansare a studiilor închise.

**Pentru reproducere:** aplicați direct formula de mai sus fiecărui rând `costContextRows` din sursa exactă; nu solicitați token-uri, nu executați ordine și nu activați Cloud.
