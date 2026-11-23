# P0.5 — Universul complet, date și frontieră economică (preliminar, 2026-11-23)

Acest raport reproduce inventarul autentic publicat anterior. **Nu este colectare nouă, validare B/C sau dovadă de profit.** Fiecare sursă de mai jos a fost consultată din main SHA dde596ed34ec5c1df7b45093c5da312d0aa2a543.

## Univers verificabil

| Sursă | Rezultat observat |
| --- | --- |
| Inventar cont Pepperstone din 2026-11-05 | 5339 simboluri ne-arhivate; 1755 vizibile; 96 contracte investigate; 5243 neinvestigate individual |
| Marje din sursa de cont | 89 contracte cu marjă raportată; 74 au marja minimă sub 200 EUR **la data observației**, NU dovadă de finanțare curentă |
| Eșantion multi-clasă separat | 18 instrumente, clase crypto, energy, equity, fx, index. Cele 18 marje unice istorice sunt sub 300 EUR, dar condițiile complete de tranzacționare și combinațiile portofoliului rămân necunoscute |
| Istoric M5 existent în arhivă | 836087 bare autentificate, 12 instrumente, 52 săptămâni. Golurile și orarele reale încă necesită reconciliere |
| Context H1 de mai devreme | 12 instrumente, 2× proxy-ul de cost de bază / mișcare mediană 37.4%–137.8%, incomplet; nu reprezintă cost all-in |

## Acoperirea M15–D1

| Orizont | Acoperire autentică | Cost complet, profit net și HARD21 |
| --- | --- | --- |
| M15 | M5 disponibil pentru 12; M15 nativ și mai multe surse vechi, dar trebuie verificate cronologic; nu presupunem lipsa instrumentelor suplimentare | NECUNOSCUT |
| M30 | M5 și surse native fragmentare; necesita reconciliere sesiune/timeframe | NECUNOSCUT |
| H1 | M5 + 12 valori de mișcare mediană publicate | PROXY INCOMPLET |
| H4 | Agregare numai după verificare sesiune, DST și bare închise | NECUNOSCUT |
| D1 | Bare zilnice numai cu calendar broker valid; nu inventăm prețuri | NECUNOSCUT |

## Reguli de interpretare
- Cele 5243 contracte fără probe NU se elimină. Datele curente pot schimba marjele sau costurile.
- Cei 18 candidați inițiali nu sunt shortlist-ul final. Se investighează întreaga listă de 5339 după executabilitate/marjă, apoi costuri.
- La H1, 1/12 au cost proxy de două ori baza >= mișcarea mediană; nici acest caz nu este imposibilitate matematică pentru tranzacționare selectivă.
- **P0 nefinalizat; P0.5 nefinalizat.** NET EUR și %, tranzacții finanțabile/săptămână, drawdown marcat la piață: **NEDEMONSTRATE**, nu zero.
- Pentru colectări autentice noi, accesul doar prin cont/sandbox autorizat și operații de citire; fără accesarea/afișarea/alterarea secretelor, fără ordine, fără Cloud, fără studiile închise relansate.
- Cererea economică urgentă: termenii contractuali actuali pentru întregul univers, adâncimea observabilă pe M15–D1, distribuția spreadurilor BID/ASK ori model pesimist explicit, mișcarea tipică pe orizont, oportunitățile NET finanțabile și frontiera HARD21/DD.

## Identificarea surselor (Git blob)
- `docs/FULL_CTRADER_ACCOUNT_INVENTORY_AUTHENTIC_20261105.json`: `c9a1e81c9f390c7b8df6873433d3b65309fa054a`
- `docs/OWNER_EXECUTED_MULTI_ASSET_COST_CAPITAL_SCREEN_20261108.json`: `64eae2006f9019212163c6956c0ba50a6e0b753a`
- `docs/EUR_ECONOMIC_PREFLIGHT_RESULT.json`: `abc08a918daa334236054045a54d14c5f4cd1930`
- `docs/AUTHENTIC_TEMPORAL_COVERAGE_20261105.json`: `c25389264188cf3daad9699bc98bd91ca8925faa`

## Reproducere
`python -m unittest research.test_p05_economic_screen` și `python -m research.p05_economic_screen`. Un workflow fără secrete execută testele pe PR și publică raportul JSON/Markdown derivat în artifact. Acesta nu poate substitui colectarea Pepperstone autentică.
