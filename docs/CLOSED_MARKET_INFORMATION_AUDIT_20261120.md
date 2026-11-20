# Auditul fluxului de informație al cBotului MXM

20 noiembrie 2026 · Baseline [`1b510ae1cf7e873b65ffaf612f9f25910b53d07b`](https://github.com/mariancradulescu/mxm-quant-cloud/commit/1b510ae1cf7e873b65ffaf612f9f25910b53d07b) · Autoritate [OWNER_SPEC.md](OWNER_SPEC.md) și [Issue #393](https://github.com/mariancradulescu/mxm-quant-cloud/issues/393).

## Ce ajunge efectiv în politica originală

| Etapă | Consumator C# la baseline | Dovadă și efect |
| --- | --- | --- |
| Date autentificate | `research/complete_policy_economics.py` → `IntegratedEconomicReplay.Run` | CVP1 #44162043538, autentificare pe contul original, hash al arhivei decriptate și recuperare de contracte din protobuf. EURUSD, GBPUSD, AUDUSD. Istoric expus [2026-05-04, 2026-07-27), cu cotații într-un interval intraday restrâns. |
| Bare disponibile | `IntegratedEconomicReplay.MarketStream` și `BarPrefix.Observe` | Prefix de 5 M5, 3 M15 și 6 H1, cu `CloseAt < at`. `CloseAt` este o oră nominală derivată din momentul de deschidere. Filtrarea după acel timestamp lasă nedemonstrată observarea unei cotații a simbolului după limita fiecărei bare. |
| Oportunitate | `NativeCompletePolicy.IsDecision`, `Describe` | Evaluare după ceas, din 15 în 15 minute. Dacă geometria și datele sunt disponibile, încearcă explicit LONG și SHORT. Nu există un eveniment structural necesar pentru a produce o direcție. Ultimele cinci M5 trebuie să fie consecutive. Din șase H1 livrate, folosește numai ultimul. |
| Context și scor | `NativeQuoteResidenceStream`, `NativeCompletePolicy.EntryFeatures` | 30 de observații BID/ASK la 30 s, agregate la medie de rezidență, schimbare târzie și deplasare. Scorul mai primește spread normalizat, raportul monetar câștig/risc și caracteristica de sesiune. Caracteristica de sesiune se calculează prin împărțire între `long` înainte de conversia la `decimal`. Valoarea este zero pe întreaga fereastră de admitere. |
| Geometrie și dimensionare | `NativeCompletePolicy.Describe`, `ExecutableTerms`, `AdvanceIntegrated` | M5 influențează amplitudinea și stopul. Extremul ultimului H1 influențează ținta. Acestea pot afecta indirect spread/volatilitate, câștig/risc și rezerva monetară, fără un vector direct al structurii. Concurența este pe un singur registru EUR300 per contraexemplu, la minimul legal. Contractul și marja observate la captură sunt condiții de simulare. |
| Intrare și invalidare | `CoherentFill`, `NativeIntegratedLifecycle.AtFill/Observe` | Următoarea cotație admisibilă poate produce o execuție simulată. Ramura `CompletePolicy` creează o teză cu familia goală. `Observe` iese imediat în acest caz, deci șirul M15 nu poate invalida o teză structurală în această politică. |
| Administrare | `ManageIntegrated`, `NativeSimulatedCloseLifecycle.Advance` | Protecție adaptivă, stop/țintă, reducerea riscului portofoliului și checkpoint de valoare a deținerii după un M15 nou. Ultimul folosește rezidența, lichidarea estimată, MFE și sesiunea. Extrema BID/ASK pe interval poate constata o traversare. Prețul de ieșire modelat vine dintr-o observație ulterioară. |
| NET EUR | `NativeFundedLedger`, `CompleteIntegrated`, `NativeCompletePolicyResearch.Book` | Registrul reconciliază închiderile și costurile modelate. Publică situația cash, equity la eșantioane, costurile, riscul comun și HARD21 calculat din închideri complete. Continuitatea equity dintre observații și execuția broker rămân necunoscute. |
| Paritate | `MxmCloud.ReadProductResearchMarket`, `ReadFullSessionMarket`, `NativeUnifiedCloudParityAdapter` | Același motor primește cadre diferite. Cloud citește `MarketData.GetBars` din timer. Calea full-session poate porni de la `Count-1` și filtra exclusiv după ora nominală. Testul sintetic anterior dovedește paritatea motorului pentru aceleași cadre. Citirea efectivă a feedului și disponibilitatea la frontieră au nevoie de probe distincte. |

**Reconciliere originală.** [Actions #44719106893](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44719106893), artefact [#14620253998](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44719106893/artifacts/14620253998). SHA‑256 ZIP `9d886ca2d292e6a616d4232e0cda9b81d4db87b16397b1a4cc97ac406ef4a9d5`. SHA‑256 `economic.json` `ab6270bf320bd9d9ae4aaa3bcb98f26875ea20fcde20231a832bb873f5255fd0`, egal cu `NativeOutputSha256` din recipisă. Suma NET a fiecărui registru corespunde atât tranzacțiilor individuale, cât și diferenței dintre cash final și 300 EUR. ECONOMIC central are 30 de închideri, NET −2,8775 EUR, cash final 297,1225 EUR și HARD21 în 0 din 4 săptămâni. Advers are 34 de închideri, NET −2,9476 EUR, cash final 297,0524 EUR și HARD21 în 0 din 4 săptămâni.

## Matricea de proveniență

Orele sursă sunt UTC. O solicitare completă la API confirmă întinderea cererii. Disponibilitatea efectivă a ferestrei se verifică separat la fiecare ceas de decizie.

| Informație | Sursă și acoperire verificabilă | Disponibilitate și limită | Consumator C# și utilizare |
| --- | --- | --- | --- |
| M1 și distribuție de activitate | HXC1 #43817213663, 111.142 bare pe patru simboluri, [2026-10-19, 2026-11-16). Protobuf `ProtoOAGetTrendbarsReq`. | OHLC și volum tick pe interval, confirmare după bară. Ordinea mișcărilor din interior rămâne necunoscută. | MRF1 a folosit M1 și agregări cauzale în studiul său închis. Zero M1 direct în `NativeCompletePolicy`. Noul `NativeClosedMarketContext` măsoară acoperirea. |
| M5, structură locală | 836.087 M5, 12 simboluri, 52 săptămâni în dovada arhivei anterioare. Separat, originalele CVP1 și full-session conțin M5 nativ pentru universurile lor. | Raportul de acoperire totală nu arată sincronia cu BID/ASK/FX și nu se adună cu ferestrele suprapuse. | `Describe` consumă cinci M5 pentru volatilitate și stop. Ultimele trei furnizează extremele. |
| M15, confirmare și invalidare | XMH2 #44352570167, 208.624 bare [2025-11-16, 2026-08-17), și HXC1, 70.867 [2026-08-17, 2026-11-16). 279.491 în cele două perioade disjuncte, 12 simboluri. | XMH2 consemnează 53 ferestre de 48 h goale. Barele lipsă rămân absente. | `AtFill/Observe` consumă trei M15 în familiile structurale. În `CompletePolicy`, M15 servește referința temporală pentru deținere, fără vot structural la intrare. |
| M30, H4, D1 | Cloud `MarketData.GetBars`, surse/derivări istorice în alte protocoale unde sunt certificate. Extinderea nativă vizează direct patru periodicități pe opt simboluri, cu reutilizare HXC1 pentru M1. | Cererile native și ferestrele disponibile se cuantifică separat. Orarul actual și intervalele lipsă nu pot demonstra sesiunile istorice. | Cloud deja verifică unele dintre aceste frame-uri în observația de warmup. Niciunul dintre M30/H4/D1 nu intră în scorul original. |
| H1, regim și niveluri | HXC1 #43817213663, 70.270 bare, 12 simboluri, [2025-11-16, 2026-11-16). CVP1 și full-session au H1 aliniat la cotațiile lor. | Marcaj nominal și martor al disponibilității pe simbol. Confirmarea a șase bare valide necesită continuitate, care poate lipsi la redeschideri. | În `NativeCompletePolicy.Describe` ultima H1 stabilește ținta sau lățimea de rezervă. Trendul interbar și contradicțiile H1/M15 nu intră în scor. |
| Volum tick, impuls, consolidare | Câmpul Open API `volume`, Cloud `Bars.TickVolumes`. OHLC nativ păstrează extreme, fără ordinea evenimentelor din bară. | Activitatea are sens în raport cu contextul simbolului. Volumul tranzacționat nu este furnizat de aceste bare. | `NativeCausalWarmup` și `MultiFamilyNativeFeatures` au consumatori proprii. `CompletePolicy.EntryFeatures` nu citește volumul tick. |
| BID/ASK, activitate și cost | CVP1, OEI1, originalul full-session #44687919474 pentru șase instrumente și cinci clase, apoi surse punctuale pe active individuale. `ProtoOAGetTickDataReq` pe fiecare latură. | Păstrează timestamp separat pe latură. Parcurgerea eșantionată pierde ordinea intrainterval și gap-urile. Un tick unic nu validează un traseu continuu. | Replay normalizează în `SourceQuote` și `NativeObservedQuotePath`. `NativeQuoteResidenceStream` consumă eșantioane, `BuildQuote` produce costuri, iar ledgerul marchează pozițiile. |
| Sesiune și intermarket | Programul din snapshotul contractului, ceasurile și cotațiile observate pe fiecare piață. Date sincronizate de instrumente pereche există punctual. | Sesiunea istorică trebuie verificată la data respectivă. Piețele lipsă pot modifica numitorul unei măsuri de breadth, iar contradicțiile depind de timestamp-urile reale. | Time-of-day fixează eligibilitatea originală. `Session` este constantă pentru intrări. Ordinea scorului original nu folosește intermarket. Contabilitatea comună nu substituie informația despre expuneri corelate. |
| Contract, marjă, comision, conversie, finanțare | `ProtoOASymbolByIdReq`, `ProtoOAExpectedMarginReq` view-only și EURUSD BID/ASK as-of pentru instrumentele USD eligibile. | Snapshotul de contract/marjă are data capturii. Finanțarea, istoricul tarifelor, fill-urile efective și rutele multi-valută incomplete rămân necunoscute în acest lanț. | `NativeBrokerContractCosts`, `NativeExecutableEconomics` și `NativeFundedLedger` consumă valorile condiționale. Pachetul original nu certifică NET de broker. |
| Depth și execuții | Open API `ProtoOASubscribeDepthQuotesReq` și evenimente live. DCP1 a conservat un eșantion foarte scurt. | Arhivă istorică comparabilă, tranzacții ale pieței, lichiditate executabilă sau prioritate la coadă nedemonstrate. | Acestea nu intră în `CompletePolicy`. Simularea folosește BID/ASK efectiv observat, costuri și ipoteze de latență/slippage declarate. |

Recipise și documentație pentru verificare. [Acoperire M5](AUTHENTIC_TEMPORAL_COVERAGE_20261105.json), [HXC1](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43817213663/artifacts/14202818396), [XMH2](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44352570167/artifacts/14449297739), [full-session](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44687919474/artifacts/14608253229), [DCP1](DCP1_CHANNEL_RESULT.md), [Spotware Bar Events](https://help.ctrader.com/ctrader-algo/documentation/cbots/cbot-bar-events/) și [Spotware Open API](https://help.ctrader.com/open-api/symbol-data/).

## Contract tehnic prospectiv

`NativeClosedMarketContext` validează aceleași ferestre în Replay și în adaptorul platformei. Pentru o decizie la `t` folosește o frontieră strict anterioară lui `t`, o cotație a aceluiași simbol la sau după frontieră și până la `t`, și o fereastră exactă cu deschideri ordonate, intervale consecutive și OHLC valid. M1–H1 folosesc grila confirmată UTC. Pentru H4/D1, timestampul nativ al succesoarei ancorează fereastra, iar valorile din bara succesoare rămân în afara contextului. Cloud exclude valorile cozii mutabile a colecției. Absența succesoarei, latența martorului, lipsa ultimei bare, un gol sau warmup insuficient sunt stări explicite. La închiderea pieței ferestrele discontinue rămân indisponibile. O ipoteză care poate traversa o închidere are nevoie de validare pe calendarul autentic al instrumentului.

Semnătura SHA‑256 a valorilor ferestrei oferă verificarea aceleiași intrări C# în fixture-ul celor două adaptoare. Replay folosește timestamp-urile laturilor separat, Cloud istoricul local `Ticks` disponibil cBotului. Probele deterministe demonstrează contractul comun pe intrări identice. Măsurarea evenimentelor platformei și a întregii parități până la NET rămâne necesară înaintea unei calificări. Censusul nou publică disponibilitatea la cotațiile autentice, cu ferestrele și sursele din matrice. Rezultatele originale și metodele lor înghețate sunt arhiva de referință.

## Captura suplimentară și recitirea originală

Actions #44733062339 a validat 480 de cereri trendbar autorizate pe opt simboluri. Recitirea inițială publică reconstruiește 147.328 de bare, dintre care 135.944 M1, 9.914 M30, 1.278 H4 și 192 D1. Include 105 pagini fără bare. NAS100 și GER40 extind acoperirea structurală a programului. Cele șase piețe cu arhivă pereche BID/ASK formează cohorta financiară a evaluării. [Actions #44733062339](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44733062339) · [Recipisa de captură](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44733062339/artifacts/14627871330) · [Recitirea inițială](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44733062339/artifacts/14627991400).

Data D1 are deschideri observate la 21:00 UTC la începutul ferestrei și la 22:00 UTC spre final. Validarea primei recitiri, care presupunea miezul nopții UTC, a respins toate contextele H4 și D1. A doua recitire folosește timestamp-urile native și include rândurile brute autentificate care traversau tăieturile convenționale ale paginilor UTC. D1 este opțional pentru protocolul de oportunități. Frecvența contextelor valide urmează dovezile pe fiecare piață.

| Membru original | SHA-256 verificat |
| --- | --- |
| `source.public.json` | `c169c743c120852d2167a866324872f255c3c9baf9cf4b09700e334a978568db` |
| Arhiva protejată `source.enc`, hash legat în recipisă | `443b2dd37d31ea2227de39a19bcce17ba1f0c0804a51483bc3e035eedb5d9d53` |
| `closed-market-context.json` din prima recitire | `eae559ddd08a42c58252eea43bbbaf47e6eecbc2efb381b8a9dc57b59a6e28f7` |

## Rezultatul original al programului integrat

PR #413 a introdus auditul și sursa. PR #414 a legat validarea de oportunitate, teză, finanțare și decontarea din portofoliul comun. Protocolul a fost înghețat în `26f74f4807356cd783658812f7cf8b2e56bb2ae8`. Evaluarea protejată a rulat pe `90568cfe38e0d7cd6ff31aebea3fb7e401ffe839` după 943 de verificări locale C#, verificarea CI și compilarea oficială cTrader CLI. Probele sintetice Replay/adaptor acoperă inclusiv decizia cu scor, cotația ulterioară de intrare, invalidarea prin M15 nou și reconcilierea în EUR. Feedul efectiv al cBotului în Cloud rămâne de verificat sub o autorizare separată. [PR #413](https://github.com/mariancradulescu/mxm-quant-cloud/pull/413) · [PR #414](https://github.com/mariancradulescu/mxm-quant-cloud/pull/414) · [CI](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44735293314) · [cTrader CLI](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44735292975) · [Original #44735700353](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44735700353).

| Piață | Observații cu BID/ASK | M1–H1 sincronizate cu limita M5 | H4 valid cu șase bare | D1 valid cu cinci bare |
| --- | ---: | ---: | ---: | ---: |
| EURUSD | 42.759 | 8.009 | 34.314 | 0 |
| GBPUSD | 42.704 | 7.969 | 34.265 | 0 |
| XAUUSD | 41.211 | 6.114 | 33.060 | 0 |
| SpotBrent | 38.270 | 5.525 | 30.136 | 0 |
| US500 | 41.236 | 6.114 | 33.081 | 0 |
| AAPL.US | 11.627 | 355 | 0 | 0 |
| Total | 217.807 | 34.086 | 164.856 | 0 |

Fiecare serie D1 din tabel are 29 de rânduri refăcute din protobuf. Ferestrele cu cinci intervale zilnice continue au rămas indisponibile din cauza golurilor dintre bare sau a lipsei succesoarei observabile. H4 este valid în fereastra cerută pe cinci piețe. H4 și D1 nu sunt intrări în scorul înghețat pentru acest studiu. Dintre ceasurile cu termeni monetari și context complet, motorul a consumat 17.067 de bare M5 noi și a găsit 481 de oportunități pe cele trei săptămâni. `OfferEvidence` permite verificarea sursei, a datei, a martorului disponibilității și a SHA‑256 pentru cele cinci ferestre consumate de fiecare oportunitate. În W46 au existat 144 de oferte pe cinci simboluri, 72 pe familie. AAPL.US a avut șase oferte în cele trei săptămâni și zero în W46.

### Portofoliul comun în W46

W44 a furnizat 177 de oferte pentru antrenare, W45 a furnizat 160 pentru calibrare, iar W46 a furnizat 144 pentru evaluare. Istoricul tuturor fazelor este expus. Fiecare rând este un registru contrafactual cu 300 EUR proprii împărțiți între toate piețele eligibile. NET include spread, comisioane, slippage și cost de conversie modelate. Finanțarea istorică și execuția reală la broker rămân necertificate.

| Politică | Închideri central | NET central EUR | Închideri advers | NET advers EUR |
| --- | ---: | ---: | ---: | ---: |
| CASH | 0 | 0,0000 | 0 | 0,0000 |
| FIRST financeabil | 88 | +4,0316 | 86 | +1,2787 |
| RANDOM | 88 | +3,9081 | 86 | +1,1694 |
| Compresie | 34 | +0,7843 | 35 | −0,4310 |
| Respingerea marginii | 56 | +7,6596 | 53 | +5,9206 |
| Distribuție comună pe familie | 88 | +4,0048 | 86 | +1,7188 |
| Clasament contextual | 88 | +8,8444 | 86 | +5,9666 |
| Admitere selectivă | 0 | 0,0000 | 0 | 0,0000 |

Clasamentul contextual încheie cu toate pozițiile închise și cu 308,8444 EUR central, respectiv 305,9666 EUR advers. NET provine din +15,4948 EUR brut și 6,6504 EUR costuri central, respectiv +15,6052 EUR brut și 9,6387 EUR costuri advers. DD eșantionat a fost 1,8743% și 2,0176%. Portofoliul a avut două poziții simultane și marjă maximă 201,5375 EUR. Au existat cinci închideri după invalidarea tezei prin M15 în fiecare scenariu. HARD21 este îndeplinit în singura săptămână de evaluare a clasamentului. Pragul de 30% trebuie verificat și între observații.

### Ce a determinat rezultatul

- Clasamentul a depășit FIRST cu +4,8127 EUR central și +4,6879 EUR advers. Au existat numai șase ceasuri cu mai multe simboluri simultan finanțabile în fiecare scenariu. Diferența de contribuție atribuită XAUUSD este +4,7518 EUR central și +4,6040 EUR advers. Celelalte piețe ale clasamentului au însumat −2,9929 EUR central și −5,0476 EUR advers. Acestea sunt contribuții din registrul executat. Un portofoliu contrafactual fără XAUUSD ar putea avea alte selecții, marjă și expunere.
- Din W46, 96 episoade centrale și 92 adverse au furnizat etichetă monetară completă pentru evaluarea modelelor. Clasamentul contextual reduce eroarea absolută în EUR față de distribuția comună, 0,4630 față de 0,4824 central și 0,4780 față de 0,4967 advers. Brier este mai slab în ambele comparații, 0,2880 față de 0,2815 și 0,2911 față de 0,2805. Admiterea selectivă a produs câte o intenție XAUUSD. Ambele au fost respinse la recotarea pentru execuție. Recipisa agregă motivele din acel filtru, astfel că variabila individuală care a invalidat fiecare intenție rămâne neatribuită.
- În clasament, trei tranzacții pe scenariu au un segment neobservat și una poate traversa o limită de finanțare neverificată. Sunt 122 ceasuri cu poziții și equity necunoscută. În scenariul advers, 11 închideri au depășit riscul planificat la intrare. Cea mai mare abatere este la US500, pierdere de 1,7416 EUR la un risc planificat de 0,7503 EUR. Comprimarea intervalului de raportare a DD la eșantioane nu recuperează riscul flotant lipsă.
- Compresia depășește CASH central și pierde 0,4310 EUR advers, când costul de 3,3198 EUR depășește brutul de 2,8887 EUR. Familia de respingere are NET pozitiv în ambele scenarii. Contribuția dominantă a aurului și orizontul de o săptămână limitează concluzia economică.

**Decizie pentru acest rezultat.** Corecția informațională este verificată în cod, prin probe și prin recitirea surselor. Avantajul economic observat este condițional pe W46 și rămâne în cercetare. Calificarea pentru utilizare cere minimum 12 luni independente, costuri și risc flotant verificabile, precum și HARD21 recurent la nivelul portofoliului. Zero ordine LIVE/DEMO. Cloud nu a fost activat. Originalele închise au rămas în custodia lor.

### Identitatea dovezilor

| Element | Legătură sau SHA‑256 |
| --- | --- |
| Original ZIP #14627239908 | [Descărcare GitHub](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44735700353/artifacts/14627239908) · `0f1828ba201db4dca6c021e36bc0724b04253c3cadd849c78c949398a973cc98` |
| `receipt.json` | `748a6f1739c9528d08faa8fae892a54d6f795d6eb7993b9176b192ac664df4b6` |
| `context.json` | `7fd4fc6b90b1fe50c2616b3b8483d35fccb7746c3d4e89904ef2be894960b460` |
| `economic.json` | `d77603ad36b989b4aa2c3a53dfa3c4323401c4553cb9ecc43793f541f17c45c9` |
| `NativeClosedMarketContext.cs` | `3d7572a53bae9845441193aaf02f67a2fb8b979e488e8235bb993e97c26bfbfd` |
| `NativeStructuralOpportunity.cs` | `8a8536b70171f46d7962322a822f3f6843dbc5187225c2eb1d7c499f6a8b5dc6` |
| `NativeStructuralResearch.cs` | `54a81fc28f1cb2cd68994e1d6cc5bd6a670d82fc1c4630d209dac07d566a530c` |

Verificarea independentă a unui registru se poate repeta din ZIP. Compară hashurile membrilor cu `receipt.json`. Pentru fiecare carte, însumează `Outcome.IndividualTrips[*].NetEur` și reconciliază rezultatul cu `Ledger.ClosedNetEur` și cu brutul minus cele patru costuri. Dacă registrul este plat la capăt, `Ledger.CashEur = 300 + Ledger.ClosedNetEur`. Pentru fiecare `REQUEST_OPEN`, localizează simbolul și ceasul în `OfferEvidence`. Pentru fiecare `OPEN_FILL` sau `CLOSE_FILL`, verifică existența intenției și ordinea temporală strictă. Core C# reconciliază separat toate evenimentele, inclusiv marcajele de cotații aflate în arhiva protejată.
