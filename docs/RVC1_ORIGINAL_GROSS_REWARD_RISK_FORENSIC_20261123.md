# RVC1 — auditul economic al calității oportunității, nu o nouă evaluare

**Mandat OWNER din 23.11.2026, după închiderea originalului RVC1.** Acest document este un diagnostic **numai din artefactul public ORIGINAL** și din citirea statică a codului C# deja integrat. Nu execută `NativeRvc1JointResidualEconomic.Evaluate`, nu decriptează/arhivează din nou sursa, nu calculează noi oportunități și nu schimbă codul, ipoteza, pragurile, contabilitatea sau rezultatul original.

## 1. Proveniență, interval, limite

- Original Actions [#45259630338](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/45259630338), prima și unica execuție, SUCCESS tehnic; [artefact original #14858829991](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/45259630338/artifacts/14858829991), doar `rvc1-original-public.json`.
- ZIP SHA-256: `1176630082c51eeb28fb1b07748bce9540e0e912a2338fe09605ad0173c85d60`. JSON SHA-256: `fb4a83ec5d542886f607600647d70f45d951b505793395db143b4398b87dd44e`. SHA-256 al întregului JSON privat (păstrat ca *angajament*, nu ca fișier de tranzacții accesibil public): `acca2741f24bd10c805b4a0dbe759619ed2dbe7349ae89a692af3352dff73359`.
- 52 săptămâni calendaristice din sursa expusă, 74.212 ceasuri M5 în reuniunea celor două instrumente; 74.195 EURUSD M5, 74.126 GBPUSD M5, 6.190 H1 pentru fiecare. Două instrumente; bare din surse autentificate, dar BID/ASK și fillurile **nu** sunt autentificate pentru fiecare tranzacție istorică.
- 4 politici finanțate **independent** cu 300 EUR fiecare, 3 scenarii de cost; nu sunt 12 bugete ce pot fi însumate. Scorarea din Python a publicat **numai agregate**, a eliminat explicit `ClosedFragments` din fișierul public; ieșirea completă privată a fost într-un director temporar șters după job. Nu există în originalul conservat un registru public individual al celor 36 fragmente închise × fiecare scenariu.
- Originalul exact rămâne `RVC1_UNQUALIFIED_HARD21_FAILURE_TERMINAL_CENSORED`; acest audit nu îl redeschide. **HARD21 este ținta sistemului final, nu un veto universal asupra oricărei idei componente.**

## 2. Rezultat BRUT: costurile nu explică singure eșecul

Politica `JOINT_RESIDUAL`: aceleași **18 perechi complete** modelate, închise în 2025-W47, în fiecare scenariu de cost.

| Cost | BRUT închis EUR | BRUT / pereche EUR | Costuri modelate pe fragmente EUR | NET închis EUR | NET / pereche EUR |
|---|---:|---:|---:|---:|---:|
| ×1 | **−2,381300** | **−0,132294** | 3,409552 | −5,790853 | −0,321714 |
| ×1,5 | **−2,337899** | **−0,129883** | 5,114348 | −7,452247 | −0,414014 |
| ×2 | **−3,245699** | **−0,180317** | 6,818309 | −10,064008 | −0,559112 |

Toate cele trei **sume brute ale pozițiilor închise sunt negative**. La ×1,5, aproximativ **31,4% din valoarea absolută a pierderii NET închise** provine din BRUT negativ și 68,6% din costurile atribuite; aceasta este o *descompunere aritmetică*, nu o atribuire cauzală. BRUT-ul diferă ușor între scenarii deși numărul perechilor este același; reprezintă componenta `GrossEur` a registrului modelat sub fiecare scenariu, **nu o măsură independentă demonstrată a alpha price-only pe tranzacții exact împerecheate**. Nu extrapolăm 18 perechi la restul celor 52 de săptămâni.

×1,5 costuri conservate: spread **1,151138 EUR**, slippage **1,151298 EUR**, comisioane **2,803844 EUR**, conversie **0,008068 EUR**; sumă 5,114348 EUR. Swap în fragmentele închise: în registru **0**, dar swap pentru perechea *rămasă deschisă* este **UNKNOWN**, nu zero dovedit.

**Comparatorul `PAIRED_NO_CONVERGENCE`** are EXACT același număr de perechi închise și același BRUT/NET total în toate cele trei scenarii. Evidența agregată arată **zero contribuție incrementală măsurată** a ieșirii prin convergență. Nu probează egalitatea fiecărui traseu sau că zero tranzacții au întâlnit centrul: fără ID-uri individuale și coduri distincte de ieșire, această deducție ar fi inventată.

`SINGLE_EURUSD` ×1,5: **+5,685680 EUR BRUT / +5,059987 EUR NET** pe **6** tranzacții single-leg închise, cu 1 încă deschisă. E un indiciu de **atribuire neidentificată a expunerii**; nu este confirmarea că ar trebui să tranzacționăm numai EURUSD, un semnal pentru inversare sau un avantaj independent.

## 3. Ce putem și ce NU putem diagnostica din original

| Cerință OWNER | Ceea ce se poate stabili verificabil | Ceea ce NU este conservat și nu poate fi calculat onest |
|---|---|---|
| Reward/risk proiectat la intrare, EUR și R | Codul `MakeLeg` rezervă `StopRisk` pe fiecare picior: distanță aproximativă `max(0,3−|z_in|)×sigma×Ask`, plus costuri; peak Held+Pending rezervat ×1,5 **2,043649 EUR** | `EntryZ`, `mu`, `sigma`, valoare țintă traductibilă în EUR, risc inițial per **pereche** și reward EUR per intrare; **R:R în EUR/tranzacție = NECUNOSCUT** |
| Profit/pierdere pereche | 18 perechi, 36 fragmente, BRUT total, NET total, media contabilă | Profit individual, pierdere individuală, număr de câștigători, win rate, raport câștig/pierdere, dispersion, profit factor; nu se deduc din sumă și N |
| Durată | `OpenedAt` și `ClosedAt` există în `LedgerClosedFragment` în outputul C# privat | Distribuția duratelor NU a fost inclusă în artefactul public; toate închiderile atribuite săptămânii W47 nu determină durata |
| Motivul ieșirii | Codul `ExitNeeded` poate solicita închiderea după convergență, deplasare adversă a raportului, drift H1, stop individual de preț, oprire DD | `SettleClose` atribuie uniform `RVC1_JOINT_RISK_OR_RESIDUAL`; motivul **real distinct** pe fiecare pereche nu a fost conservat |
| MFE/MAE | Source are observații M5 autentice în ferestre, dar valorile de execuție sunt modelate; pot exista mark-uri în ledger | Engine-ul RVC1 **nu înregistrează** MFE/MAE separat pe **pereche** și nu publică mark-urile individuale; nu reconstruim un traseu *după expunerea rezultatului* |
| Influența convergenței | Diferit de CASH, dar egalitate agregată cu `PAIRED_NO_CONVERGENCE`; **increment observat 0** pe tranzacții închise | Număr ținte atinse vs stop; event-wise perechi matching; contrafactual `HOLD` pentru aceleași intrări; nu este identificabil |
| Teză greșită vs management / implementare | BRUT negativ al fragmentelor închise; criteriul țintă nu aduce contribuție agregată; blocarea terminală este implementare/sursă | Nu putem aloca pierderea `−2,337899` către intrări greșite, ieșiri precoce, martorii de convergență sau hedging fără seria de episoade |
| Capital/eligibilitate | 19 perechi deschise modelat, 18 închise; o pereche terminală Held + 2 CLOSE Pending; 51 săptămâni cu zero închideri | Frecvența oportunităților ce **ar fi** fost finanțabile după închiderea perechii terminale: nu este măsurată în original |

**Important:** `SourceClocks=65` în 2025-W47 sunt **clocks de decizie numărate doar când politica este flat**, nu toate evenimentele posibile după intrarea în blocaj. Nu le interpreta ca inventar anual de semnale.

## 4. Problemă economică înaintea costului: raportul z nu este payoff EUR

Semnalul folosește `ln(EURUSD/GBPUSD)`; o deviatie `|z|≥1,5` nu înseamnă automat un raport reward/risk pozitiv în EUR. Codul construiește laturile la **volumele minime legale independente** (fără calibrare a noționalelor USD). Modificarea profitului brut aproximativ este `−u_E×ΔEURUSD + u_G×ΔGBPUSD` pentru z pozitiv, convertită în EUR; dacă `u_E×EURUSD ≠ u_G×GBPUSD`, expunerea reziduală la USD rămâne în portofoliu. Nu avem în artefact valoarea **reală, intrare cu intrare** a acestei nepotriviri.

Cu o țintă de revenire la `mu` și o barieră la `|z|=3`, **doar în spațiul normalizat** raportul distanțelor se poate scrie ilustrativ `|z_intrare|/(3−|z_intrare|)` pentru `1,5≤|z|<3`. Aceasta **nu** este valoare de reward/risk finanțabilă, nici profit proiectat în EUR, nici probabilitate de reușită. Stopurile individuale sunt calibrate separat prin `price×(3−|z|)×sigma`; un stop de preț pe un singur instrument poate declanșa închiderea ambelor picioare chiar dacă raportul economic nu s-a invalidat. Este posibil ca o parte a mișcării profitabile să fie pierdută sau ca o pereche care revine la centru să nu câștige bani. **Nu afirmăm că s-a întâmplat în cele 18 închideri**, fiindcă traseele lipsesc.

### Arhitectura MFE/MAE
Pentru cercetarea prospectivă, distanța țintă și cea adversă se calculează în **EUR al pozițiilor legal finanțabile** după ce sunt cunoscute dimensiunea și alocarea ambelor picioare; R este `profit/protective_loss_initially_frozen_eur` pe *pereche*, nu `sigma` sau pipurile unui singur picior. Ofertele LONG/SHORT/WAIT/CASH și deciziile HOLD/REDUCE/CLOSE trebuie evaluate pe stări de capital comun cu aceleași oportunități. MFE/MAE trebuie actualizate **pe mark-uri cauzale efectiv observate după fill**, fără extreme de lumânări încă neînchise, cu ferestre lipsă marcate `UNKNOWN`. MFE/MAE realizate ulterior sunt **diagnostice**, niciodată informații disponibile înaintea deciziei.

## 5. Blocarea ultimei perechi: o cauză tehnică, nu pierderea ipotezei

- `recovered_official_funding()` încerca să găsească programul swap EURUSD/GBPUSD în originalul P05, dar `P05 marketCoverage` (48 instrumente) **nu** cuprindea cele două simboluri; originalul public raportează **`RecoveredSwapScheduleSymbols=[]`**.
- În Core `FundingCost`, după trecerea unei ore autentice de rollover, lipsește contractul; întoarce `false`. `SettleClose` păstrează **ambele Held**, chiar dacă există intenții de CLOSE și cotații modelate ulterioare, pentru că pretinde dovada completă a swapului înaintea unui `CLOSE_FILL`.
- ×1,5: **140.782** tentative de marcare cu `MARKED_EQUITY_FUNDING_UNKNOWN`, **70.390** refuzuri de close prin `ROLLOVER_CONTRACT_UNKNOWN`; aceste contoare sunt evenimente repetate, **NU 140.782 pierderi sau tranzacții**. **102** mark-uri fără dovadă completă, **103** suspendări temporare. Se încheie cu **2 Held, 2 Pending CLOSE**, fără pending OPEN și fără noi admiteri.
- ×1,5 capitalul închis în numerar **292,46975 EUR** și `ClosedNet=-7,452247` reconciliate cu debitul de intrare încă deschis **0,078003 EUR**; `LiquidationEquity≈355,546307` **nu** este un profit de +55 EUR: e expunere rămasă, mark eșantionat și swap nedeterminat.
- `HardStops=0`, DD eșantionat **7,401%**, vârful de marjă Held+Pending-open **73,29 EUR**. Oprirea procesului de cercetare după săptămâna W47 nu s-a datorat unei încălcări observate de DD30 sau imposibilității minime a marjei. A fost în principal **un deadlock de custodie-swap al politicii de ieșire**.

### Principiu corect pentru viitoarea implementare — FĂRĂ a reinterpreta RVC1
Când o ieșire protectivă este justificată prin preț/riscul sistemic și există un **nou martor executabil**, motorul trebuie să poată solicita și procesa CLOSE chiar dacă un swap vechi nu poate fi reconciliat. Registrul trebuie să conserve **separat o datorie de finanțare `UNKNOWN`**, să marcheze NET/echity final ca **NECERTIFICATE** și să interzică numărarea tranzacției ca **decontată financiar complet** până la recuperarea costului. Nici zero swap implicit, nici poziție blocată la infinit, nici capital eliberat înainte de fill. Acesta este un contract pentru dezvoltare **prospectivă**, nu o autorizație să relansăm originalul.

## 6. Ce învățăm din RVC1 și din dezvoltarea deja făcută

1. **Primul criteriu este oportunitatea economică BRUTĂ:** venituri/perderi exprimate în EUR raportate la riscul ex-ante, nu un scor de `z`, clasificator sau procent de semnale. În primele 18 închideri RVC1, brutul este negativ; acest lucru trebuie separat de supraestimarea costului.
2. **A doua problemă este că intrarea și ieșirea nu formează aceeași teză economică:** RVC1 se deschide pe dispersia logaritmică între două valute, dar aplică protecții pe fiecare preț și nu conservă o estimare de reward în EUR a perechii. Câștigul așteptat și pierderea tolerată sunt două unități necomensurabile până la dimensionarea legală.
3. **A treia problemă este incapacitatea de a identifica câtă valoare adaugă gestionarea:** perechea FULL și NO_CONVERGENCE au aceeași ieșire agregată. Fără motive individuale și traiectorii MFE/MAE, orice retunare a ieșirilor pe baza celor 18 rezultate ar fi un diagnostic inventat.
4. **A patra problemă este concentrarea și cenzurarea:** 19 intrări și 18 închideri în 2025-W47 nu sunt 52 săptămâni de test economic cu opționalitate; o obligație de finanțare nerecuperată a sechestrat perechea și opțiunile ulterioare. Nu eliminăm mecanismele distincte doar pentru că nu pot singure livra HARD21.
5. **A cincea problemă este arhitectura repetării măsurătorilor:** repository-ul ARE deja `NativeUnifiedPortfolioEngine` / `Ucp1Episode` cu `EntryRiskEur`, `R`, `SampledMfeEur`, `SampledMaeEur`, `ExitReason` și `NativePerformanceScorecard` pentru expectancy, win rate, wins/losses, drawdown. RVC1 a implementat **un motor separat** fără a exporta acești martori. Dezvoltarea trebuie să refolosească aceste capacități într-un **singur Core**, nu să inventeze încă o colecție de variante. `NativePerformanceScorecard` numără **PositionId individual**, deci necesită o etapă de grupare **pe pereche economică** înainte de scorarea strategiilor hedged; 18 perechi NU sunt 36 oportunități.

### Dovezi economice deja obținute în celelalte programe — fără relansare

- **W44–W45**, raportul conservat `research/FUNDED_ACTION_VALUE_PROSPECTIVE.md`: comparatorul `COMBINED` advers a trecut de la **+26,4245 EUR BRUT** în W44 la **−15,8892 EUR BRUT** în W45, pe când costurile au variat numai de la **21,0762 EUR** în W44 la **22,7487 EUR** în W45. Modificarea BRUT de **−42,3137 EUR** explică majoritatea inversării de NET **−43,9863 EUR**. Aceasta demonstrează că problema principală poate fi **pierderea avantajului brut când regimul se schimbă**, nu doar fricțiunea tranzacțiilor. Nu folosim săptămâna favorabilă pentru un filtru retrospectiv.
- **MVO1**, raportul `research/MVO1_ORIGINAL_ECONOMIC_RESULT_READBACK_20261119.md`: politica `MARGINAL_CAUSAL` a produs **−0,448893 bps** price-only mediu pe 1.304 completări, în timp ce `FIRST_ADMISSIBLE` are **+0,578611 bps** pe 1.257, înainte de costuri. Mai mult, 72 episoade cu goluri de observație au contribuit peste totalul BRUT pozitiv al `FIRST`; acea medie **nu demonstrează alpha executabil**. Complexitatea selectorului nu justifică ignorarea unui control simplu și a riscului cenzurat.
- **FPE1**, `research/PAV1_FPE1_READONLY_MARGIN_FORENSIC_20261123.md`: `Fundable()` nu rezerva simultan **Held + Pending** la admisie. Un număr mai mare de oportunități fără respectarea continuă a finanțării poate fi fictiv; corecția capitalului este o condiție de **credibilitate a payoffului**, nu o sursă de avantaj.
- **RVC1** completează diagnosticul: ipoteza de valoare relativă poate fi interesantă, dar nu este suficient un semnal `z`; trebuie dovedit **payofful exact al perechii, R/risc în EUR, plus valoarea incrementală a EXIT față de HOLD și CASH**, fără blocare tehnică a portofoliului.

În toate aceste cazuri, concluzia corectă este **nu avem încă avantaj BRUT recurent, stabil și cu distribuție de pierderi controlabilă**, nu `brokerul are spread prea mare` și nici `este imposibil să existe alpha`. Datele originale măsoară *anumite configurații*, nu toate mecanismele viitoare.

## 7. Cerința prospectivă — instrumentare, nu serie nouă de strategii

Înaintea oricărei alte evaluări cu bani modelați, **un unic sistem C#** trebuie să conserve obligatoriu, cu o entitate `EconomicEpisodeId` pentru perechi/poziții:
- **La admiterea cauzală:** hash sursă/protocol, bar-close decisionTime, disponibilitatea tuturor contextelor, motivul semnalului, volume legale și nepotrivirea noțională, `RewardEur` **proiectat** (cu ipoteză explicită, nu promisiune), `RiskEur` proiectat, reward/risk în R, poziții concurrente/WAIT/CASH, marja Held+Pending, stress post-fill, stop/thesis și probabilitatea calibrată numai când există dovezi anterioare;
- **La fiecare observație în timp real / replay:** quote/mark **causal**, Held/Pending, lichidarea estimată pe pereche, MFE/MAE EUR și R **cenzurate la goluri**, dinamica riscului, poziție/hedge residuală, motivul fiecărei hotărâri HOLD/REDUCE/CLOSE, schimbarea oportunității de continuare;
- **La finalizarea fiecărei perechi:** per-leg și per-pair gross, net dacă este complet finanțabil și demonstrabil, comisioane/spread/slippage/swap/conversie distincte, timestamp-uri, durată, criteriul care a determinat închiderea, atingerea barierelor fără `hindsight` la intrare, câștig/pierdere în EUR, `R_{ realizat}`, censored/swap-unverified ca rezultate distincte, nu false zero.
- **Raportul unic de portofoliu:** distribuția completă a câștigurilor/pierderilor pe **episoade economice**, probabilitate de succes numai pe eşantion adecvat, payoff/profit factor, downside tail, gross expectancy EUR și R, incremental LONG/SHORT/HOLD/REDUCE/CLOSE față de WAIT/CASH pe aceleași oportunități, contribuție reală a managementului, capital comun EUR300, dd floating observat vs necunoscut, marja Held+Pending și numărul de săptămâni cu 21 **tranzacții finanțate complete** numai la nivel **sistemic**.

**Falsificări metodologice**: respinge orice nou raport în care `RewardEur` este înlocuit cu sigma, R:risc este dedus doar din ATR, numerele de picioare sunt numărate ca perechi, sursa lipsește dar markul este considerat continuu, închiderea protectivă este imposibilă doar fiindcă swapul e unknown, o poziție nu poate fi încadrată `censored`, sau se evaluează rezultate viitoare pentru decizii trecut.

**Nu începe niciun alt screening, nici PEL1, nici RVC1 rescorat; nu deschide un program nou de strategii pe baza acestui diagnostic.** Toate datele 2025–2026 sunt DEVELOPMENT. Validarea independentă ulterioară rămâne o etapă separată. Zero ordine LIVE/DEMO, zero Cloud, zero secrete modificate.

## 8. Verdict al auditului economic RVC1
`RVC1_ORIGINAL_CLOSED_NET_GROSS_NEGATIVE__MANAGEMENT_ATTRIBUTION_UNKNOWN__TERMINAL_PROTECTIVE_DEADLOCK`.

Această concluzie **NU** afirmă `win rate=0`, `RR<1` pentru fiecare tranzacție, `MFE=0`, `18 pierderi` ori că strategia relațională nu poate funcționa niciodată. Niciuna nu este susținută de original. Rezultatul exact rămâne conservat; refuzăm atât cosmetizarea prin scăderea costurilor, cât și atribuirea falsă a unei strategii complet infirmate numai pe registrul cenzurat.
