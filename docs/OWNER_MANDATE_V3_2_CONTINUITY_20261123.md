# MXM — Mandat tehnic și economic V3.2, CONTINUITATE în repository-ul existent

**Statut: V3.2 — DE TRANSMIS EXPLICIT DIRECTORULUI, valabil pentru repository-ul existent `mariancradulescu/mxm-quant-cloud`; nu creează un repo nou.** Versiune derivată fără schimbarea obiectivelor economice din V3.1 (revizie 23 noiembrie 2026, surse oficiale Spotware/cTrader, Pepperstone și GitHub). Intră în vigoare când OWNER îi transmite acest document Directorului. Înlocuiește dispozițiile conflictuale ale mandatului inițial numai prospectiv; conservă studiile originale, rezultatele negative și perioadele deja expuse. Nu autorizează ștergeri, mutarea secretelor, ordine sau activarea Cloud.

**Obiectiv:** să stabilim dacă un singur cBot C# autonom, executabil în **cTrader Cloud**, poate produce **avantaj NET robust după toate costurile**, plecând de la **300 EUR capital comun continuu**, realizând natural **HARD21: minimum 21 tranzacții complete/finanțabile în fiecare săptămână eligibilă**, cu **drawdown pe equity marcat la piață ≤30%**, fără informație din viitor. Dacă nu există dovadă, rezultatul corect este **NU ESTE DEMONSTRAT** sau, unde avem dovadă contrară, **RESPINS**. Nicio promisiune de profit.

**Surse de autoritate:** numai documentațiile oficiale Spotware/cTrader, Pepperstone și GitHub (pentru administrarea CI/securității), plus răspunsurile autentice ale contului/brokerului. Orice hotărâre OWNER privind obiectivele este o **cerință**, nu un fapt verificat. Sursele oficiale atestă capabilități API, **nu** că un anume istoric, cost sau rezultat economic este disponibil în contul Pepperstone. Toate referințele [Sxx] sunt listate la final.

**REGULA OWNER V3.2 — NU REINVENTA CAPABILITĂȚILE OFICIALE.** Dacă Spotware documentează explicit că o funcție Algo API/CLI este disponibilă în **Cloud**, o consemnezi drept **CAPABILITATE OFICIALĂ CONFIRMATĂ**, cu URL și condiții, **fără să inventezi microteste sau experimente dedicate pentru a o reconfirma**. Verificările sunt rezervate (a) codului propriu și integrării lui, (b) limitelor cantitative/de cont care nu sunt garantate oficial, (c) securității tokenului și (d) corectitudinii financiare, cauzalității, warm-up-ului și parității. Nu confunda „API oficial disponibil” cu „implementarea noastră este corectă” sau „modelul este profitabil”.

## 1. Ordine de prioritate și roluri

1. Securitate și **zero ordine LIVE/DEMO** în timpul proiectului; zero pornire Cloud de către agent; zero divulgare de chei.
2. C# **Cloud-capable** verificat din prima zi, nu o strategie Python care ulterior „ar trebui convertită”.
3. Date autentice și decizii strict cauzale; bariere metodologice contra supraînvățării.
4. Net economic, costuri, marjă, 300 EUR/HARD21/DD; păstrarea tuturor rezultatelor inclusiv negative.
5. Cost operațional minim, workflow-uri puține, criterii clare de oprire.

**DIRECTOR** = unicul executant GitHub și al testelor istorice. **AUDITOR** = verifică independent și nu scrie simultan în repository. **OWNER** = nu alege algoritmi, ci numai autorizează operațiuni rezervate contului său și decide personal dacă încarcă/pornește cBot-ul final. Niciun agent nu transmite automat mesaje altui chat.

## 2. Separarea riguroasă a celor trei medii

| Mediu | Ce face | Acces și interdicții |
|---|---|---|
| **Cercetare GitHub Actions** | Descărcare oficială de istoric, explorare, teste, compilare, backtest | Open API prin citire numai; poate citi din contul LIVE **fără a plasa ordine**; niciun acces la execuție de ordine. Fără `ctrader-cli run` [S04][S05][S06]. |
| **cTrader CLI, backtest** | Rulează `.algo` numai pe date istorice, furnizează rapoarte de paritate | `build`/`metadata`/`backtest`; autentificarea CLI cu cTID/fișier de credențiale este **diferită** de tokenul OAuth Open API [S07][S08]. Niciodată `run`, `stop` de cont, `orders`, `execute` sau alte comenzi care schimbă contul. |
| **cTrader Cloud, produs final** | După decizia OWNER, cBot-ul citește piața/pozițiile și poate transmite ordine prin **API-ul nativ Algo** | Nu necesită tokenul Open API de cercetare. Cloud nu este pornit de Director. La pornire, un cBot final cu logică de execuție **poate tranzacționa efectiv**; butonul Start este o decizie reală de risc [S01][S02]. |

**Corecție esențială:** un token Open API cu scope `trading` **permite tehnic ordine**, chiar dacă îl folosim intenționat doar pentru date. Alegerea preferată este `accounts` (view-only); dacă OWNER încarcă același token `trading` creat deja, acesta poate fi folosit **numai** într-un colector care transmite exclusiv mesaje de autentificare/citire, prin allowlist strictă, testată automat. Un blocaj din cod limitează comportamentul *acelui colector*, dar **nu retrage permisiunea tokenului**. Nu susține că tranzacționarea este posibilă numai prin Cloud. [S05][S06]

## 3. Continuitate: un singur repository și dovezi conservate

**Repository unic de lucru: `mariancradulescu/mxm-quant-cloud`, ramura de integrare `main`. NU se autorizează un repository nou, nici clone/fork/reset al cercetării.** DIRECTOR lucrează numai în acest repository, pe ramuri și PR-uri; AUDITOR citește/verifică independent. HEAD-ul și starea PR-urilor se recitesc LIVE înaintea modificărilor — niciun SHA istoric nu devine automat HEAD curent.

**Inventar și reutilizare prudentă:** păstrează componentele C# Core/Replay/Cloud, protecțiile read-only, colectorii, sursele și testele care au dovezi de funcționare; corectează minim numai defectele demonstrate. Nu reutiliza ca „model validat” o strategie veche doar pentru că are cod sau CI verde. Orice componentă rămasă incompletă se izolează de calea de execuție; nu se șterge, nu se rescrie istoria și nu se relansează cercetările închise.

**Stare verificată la 23.11.2026, informativă:** PR #424 integrat; colectarea autentificată read-only #45134137836 este `SUCCESS` cu artefacte publice și sigilate, inclusiv date istorice noi; PR #423 este Draft, neintegrat. Numerele, acoperirea, integritatea și costurile trebuie citite din artefactele originale înainte de utilizarea economică, nu dintr-un rezumat. Cele opt workflow-uri vechi `Queued` nu devin justificare pentru un restart; anulează-le numai prin funcții administrative sigure disponibile, fără ștergeri de dovezi și fără a bloca P0.5 dacă sunt independente.

**Regulă anti-bias:** o colectare nouă, un nou model sau o altă ramură nu transformă perioadele deja cercetate în validare „oarbă”. Perioadele și ipotezele expuse rămân dezvoltare; split-ul A/B/C existent în PR #423 se reconciliază și se îngheață *înainte* de confirmare. Dacă B/C nu sunt încă disponibile cronologic, declară `NOT_AVAILABLE`; nu inventa istoric și nu folosi B/C pentru retuning. Păstrează registrul tuturor ipotezelor încercate și corecțiile pentru comparații multiple.

**Alinierea mandatului:** acest document V3.2, însoțit de ordinul OWNER de transmitere, este autoritatea prospectivă pentru metode și arhitectură. Cerințele de fond rămân neschimbate: EUR300 continuu, HARD21, DD floating ≤30%, robustețe NET, ≥12 luni de confirmare autentic independentă, zero ordine în cercetare. Studiile deja închise își păstrează propriile protocoale și rezultate originale. Nu migra/șterge secretele ori schimba setările repository-ului fără un ordin OWNER separat.

## 4. Regula care previne construcții incompatibile cu Cloud

**Cloud-first începe în P0, dar FĂRĂ probe redundante de funcționalitate Spotware.** Directorul alcătuiește o matrice scurtă **CERINȚĂ → API oficial (URL) → suport Cloud → condiții** pentru funcțiile necesare, cum sunt `MarketData.GetBars(timeframe, symbol)`, `Bars.LoadMoreHistory`, `Symbols`, `Positions`, `Account` și evenimentele de bară [S01][S09][S10][S11][S12][S13]. Prezența explicită a etichetei **Cloud** în referința oficială este suficientă ca dovadă a **capabilității platformei**: **NU se creează un cBot-sondă, workflow sau test izolat care doar demonstrează din nou o funcție documentată**. Ulterior, la primul cod C# necesar efectiv cercetării, se verifică doar **build-ul propriu**, compatibilitatea dependențelor, logica, tratarea erorilor și interacțiunile dintre componente; aceste verificări **nu sunt retestări ale Spotware**. Nicio arhitectură nu se bazează pe caracteristici nedocumentate ca disponibile în Cloud.

*Cloud confirmat oficial:* sistem Linux; numai dependențe cross-platform și biblioteci referite la compilare; fără `Assembly.Load()` de DLL extern; HTTP nu trimite cereri; API `File` inoperant; `LocalStorage` doar memorie pe durata sesiunii; resursele și fișierele dispar la restart; WebSocketClient are limita portului 25345 în cloud de producție [S01]. Nu se folosește niciunul pentru decizie, model sau persistență.

*Cloud confirmat oficial:* accesul la date multi-simbol/multi-timeframe prin `MarketData.GetBars` și `Symbols`; bar history prin `LoadMoreHistory`; evenimentele `BarClosed` apar **doar când sosește primul tick al barei următoare**, inclusiv peste weekend, deci nu există un semnal „la fix” doar pentru că a trecut ora [S09][S10][S11]. API-ul permite utilizarea mai multor simboluri într-un cBot; **nu există în documentație o garanție că se pot încărca simultan mii de simboluri cu oricât istoric**. Universul cercetării poate fi mare; **universul live se limitează la componentele validate și încărcabile Cloud**, stabilit înainte de confirmare.

*Cloud confirmat oficial:* numai cBot poate rula în Cloud; instanță live poate rula 24/7 până la oprire/eroare; reguli privind instanțele depind de broker, documentația menționează maximum 10 pentru LIVE și 1 pentru DEMO și maximum 7 zile pentru instanțele DEMO [S02]. Nu presupune funcționarea neîntreruptă fără reconectări/restarturi.

## 5. Secrete, autorizare LIVE numai pentru citire

1. **Reutilizează exclusiv secretele deja instalate în GitHub Secrets/Environment Secrets ale repository-ului existent**, numai prin workflow-ul protejat de citire deja verificat; nu cere reintroducerea lor și nu creează altele. Directorul nu le citește, afișează, exportă, verifică prin dump, modifică sau tipărește în loguri. Nu modifica permisiunile ori mediile securizate fără o autorizare separată.
2. Pe PR și push obișnuit: **fără secrete**, CI static și teste sintetice. Accesul brokerului: numai workflow de colectare read-only autorizat explicit din `main`/SHA protejat, cu permisiuni GitHub minime, `concurrency` și timeouts, fără artefacte private publicate. Faptul că un PR este integrat nu autorizează singur o colectare nouă cu secrete.
3. Un modul UNIC de transport Open API: **deny-by-default**; permite numai mesajele oficiale necesare autentificării și **citirii** efective: simboluri, specificații, trendbars, tick-uri, quotes și date de cont permise. Nu permite, nu importa și nu folosi mesaje de ordin nou, modificare, anulare, închidere de poziție ori alte operațiuni cu efect de tranzacționare. Verificarea mesajelor este înainte de serializare/transmisie. Testele negative verifică **protecția scrisă de noi** (nu capabilitatea Open API) și resping orice mesaj necunoscut; orice cerere oficială de citire suplimentară se admite numai după clasificare și revizie explicită. Comanda CLI `run` și orice comandă de tranzacționare sunt blocate în CI. Allowlist-ul nu retrage dreptul real al tokenului `trading`: este un control software cu risc rezidual documentat.
4. Exclude înregistrarea identificatorilor personali de cont, a balantei reale, a cheilor, a răspunsurilor brute sensibile și a datelor cu licență de redistribuire incertă într-un repo PUBLIC. Date broker brute se păstrează separat în spațiu autorizat, cu hash și acces controlat. Doar rapoarte agregate publice.
5. Pentru colectările **ulterioare**, păstrează/verifică garanțiile read-only ale transportului existent (testele pentru cereri de ordin și cadre brute), fără a reconstrui autentificarea. Dacă se schimbă transportul/allowlist-ul sau lipsește dovada de securitate, **nu conecta tokenul `trading`** până la verificarea schimbării. Raportează ce operațiune OWNER ar fi necesară; nu inventa secrete. GitHub avertizează că mascarea nu este garantată și că secretele pot fi expuse de cod cu drept de scriere [S16][S17].

## 6. Surse și disponibilitate reală

1. P0 inventariază din răspunsurile oficiale Open API toate **simbolurile accesibile pe cont**, grupuri, `symbolId`, caracteristici, sesiuni și perioade. „Vizibil”, „tranzacționabil”, „finanțabil la volumul minim” și „eligibil după risc” sunt **patru stări distincte**. Nu presupune nici număr de simboluri, nici disponibilitate/istoric uniform.
2. Open API oferă `ProtoOAGetTrendbarsReq`, `ProtoOAGetTickDataReq` cu tip BID/ASK; ticks în tranșe de **maximum o săptămână per cerere**, cu limită de rezultate dependentă de backend și paginare conform răspunsului; max. **5 cereri de istoric/s/connection**, **50 nonistorice/s/connection** conform documentației oficiale, dar colectorul folosește o rată conservatoare cu retry/backoff [S04][S14]. Limita intervalului barelor depinde de timeframe.
3. Datele istorice „autentice” includ proveniență și integritate, dar *nu implică* automat costuri de execuție reale sau swap istoric pentru fiecare tranzacție. Spread-ul executabil, comisionul, conversia, finanțarea și marja istorice se certifică numai pentru ce API-ul/brokerul a observat efectiv.
4. Din cBot, `MarketData.GetBars`, `Bars.LoadMoreHistory`, `Symbol.Bid/Ask`, `VolumeInUnitsMin/Step`, `GetEstimatedMargin` și `Positions.FindAll` sunt documentate ca funcții disponibile în Cloud; **nu presupune** că istoria din Open API va fi identică cu istoricul servit la warm-up în Cloud fără test de paritate [S09][S10][S12][S13].
5. Toate datele au UTC, timestamp când au devenit disponibile, tip BID/ASK/mid, sursă, symbolId, timeframe, OHLC, tick-volume numit ca atare, calendare și DST, verificări duplicate/gaps și hashes. Nu completa golurile de observație prin prețuri inventate. Se acceptă **model de cost estimat**, dar nu observații de piață fabricate.

## 7. Costuri oficiale Pepperstone și estimări prudente

Pepperstone descrie oficial conturi **Standard** și **Razor** și structură de cost diferită: Standard include de regulă costul în spread (cu excepții, precum acțiuni); Razor FX și XAUUSD au spread brut și comision, cu finanțare overnight separată. Spreads sunt variabile. Site-urile regionale pot afișa valori diferite; **răspunsul contractual al contului utilizat și termenii entității care îl administrează au prioritate** față de tabelele generice [S15]. Nu înscrie o taxă fixă „pentru tot Pepperstone”.

Pentru fiecare simbol, sesiune, orizont și mărime reală de poziție:
- **Observat:** BID/ASK simultan când există; comisioane/volume/swap/FX/marjă oficial confirmate pentru data aplicabilă.
- **Estimare etichetată:** dacă lipsesc perechi istorice, model de spread pe simbol × sesiune × volatilitate calibrat pe mostre BID/ASK autentice cu timestamp. Media simplă poate fi **indicator descriptiv** și punct de pornire, dar **nu este „marjă de siguranță”**; folosește și dispersia, cuantilele/limitele conservative (de exemplu p90/p95 sau interval explicit) dacă proba le permite. Cu puține observații, nu inventa cuantile stabile: extinde incertitudinea/stresul și etichetează verdictul condițional. Pentru slippage și gapuri, scenarii separate; swap necunoscut nu devine zero nejustificat.
- **Scenarii comparabile:** central ×1, advers ×1,5, sever ×2 aplicate explicit componentelor VARIABILE modelate (spread/slippage), plus comision, swap/finanțare și FX separat. Nu dubla comisioane deja incluse în spread; nu trata min. spread publicitar ca preț obișnuit. Arată și **pragul de cost de break-even**, la care NET devine zero; dacă edge-ul rezistă la costuri conservatoare, cifrele îl vor demonstra.
- **Clasificarea verdictului:** `NET_MODELAT_CONDIȚIONAL` când există costuri estimate; `NET_VERIFICAT_ÎN_LIMITA_SURSEI` doar pentru condiții probate; `NECERTIFICAT` când un cost sau un fill esențial nu poate fi delimitat. Absența BID/ASK tick complet **nu blochează screeningul** și studiile condiționale, dar nici nu autorizează profit certificat.

**Regula matematică de bază:** `E[NET] = rata_de_câștig × câștig_mediu − rata_de_pierdere × pierdere_medie − costuri_totale`. R:R bun și money management prudent nu garantează avantaj; costul poate depăși un profit brut mic sau un sistem cu multe pierderi. Fiecare politică trebuie să depășească CASH **după** costuri, fără a forța frecvența.

## 8. Screening rapid universal, fără capcana „cost/mișcare”

**P0.5:** pentru toate instrumentele cu date și contract disponibil, tablou pe M15/M30/H1/H4/D1 (și alte timeframe-uri justificate). Calcul cost complet/p50/p90 mișcare autentică și cost exprimat în EUR per volum minim, plus disponibilitate, marjă, quote-age și reacție la cost ×1/×1,5/×2. Nu declara un instrument imposibil doar fiindcă media/mediana mișcării este apropiată de cost. Acest raport doar prioritizează colectarea și elimină EXCLUSIV cazuri cu imposibilitate verificată (de exemplu volum legal minim > capacitate financiară chiar înainte de risc).

**Frontiera HARD21:** pentru portofoliul comun EUR300, raportează în fiecare săptămână eligibilă: ocazii economice diagnostice, ocazii realmente identificabile în timp real, ocazii finanțabile cu marjă/risc, și tranzacții *complete, închise*, NET pentru o politică strict cauzală. Hindsight este diagnostic superior, **nu strategie** și nu confirmă HARD21. Dacă statistica nu permite concluzia, verdict `NECONCLUDENT` și spune ce colectare ar clarifica; fără șiruri infinite de teste.

## 9. Contractul simulatorului economic comun C#

Un singur `Core` C# calculează: decizia, trăsături, model înghețat, alocare, riscul, execuțiile condiționale, spread, comision, slippage, swap, FX, garanții/marjă, minimum/step, stop-out, equity FLOATING și NET, folosind feedul cronologic real. `sim/` îl folosește, `cbot/` îl folosește; Python poate colecta date și produce rapoarte statistice independente, **dar nu dublează contabilitatea autoritativă**.

Semnale exclusiv din bare închise **după** primirea evenimentului/cotației care le certifică. Fill-ul cel mai devreme la următoarea ofertă executabilă ASK/BID care există în replay; dacă nu există, refuz/UNKNOWN, nu „închidere la prețul dorit”. Stop/limit și gap cu preț nefavorabil. Mark-to-market în timpul poziției inclusiv estimare prudentă de maxime intrabar. Fără capital separat pe instrument, fără reset între săptămâni. Primele teste sunt tranzacții-caz calculate manual și verificate independent, apoi testare pe date reale.

## 10. Nucleu decizional executabil și gestionarea pozițiilor

Acțiuni: `LONG`, `SHORT`, `WAIT`, `HOLD`, `REDUCE`, `CLOSE`, `ALLOCATE`. Intrare numai cu estimare NET **peste cost + marjă de incertitudine** și volume finanțabile; selecție globală concurentă pe marjă/correlation/risc. Poziții preexistente: nu deschide duplicate; reconciliază din `Positions.FindAll(label, symbol, side)` și `Account` după reboot. Pentru REDUCE/CLOSE, compară valoarea economică a continuării cu realizarea/riscurile și include costuri; protecții dure independente de model. Timpul deținere este fallback, nu generator de tranzacții.

Regulile de risc trebuie să includă: risc maxim pe poziție, pe instrument și pe grup corelat; plafon expunere și marjă liberă; oprire preventivă sub DD critic; STOP dacă preț, calendar, volum ori spread nu sunt valide. Hard stop/SL/TP numai cu capabilități native testate și conforme ordinelor, iar redeschiderile trebuie să fie idempotente. **Nu presupune că SL sau limita DD pot garanta 30% în fața gapurilor/slippage**; certificarea se bazează pe scenarii și dovezi, nu pe un ordin stop.

## 11. Causalitate, model și warm-up fără stare ascunsă

Feature-uri și decizii numai din date disponibile `as-of`; verifică trunchierea viitorului, mutarea unei bare, date intermarket întârziate, timpul publicării, maturitatea labelului, DST/weekend. Modelul final este compilat în C#, nu descarcă coeficienți și nu antrenează în Cloud. Context maxim `N` bare/timeframe/symbol, calculat identic după `LoadMoreHistory`; validarea startup necesită cel puțin N bare, lipsă gapuri inexplicabile, sesiune deschisă și spread admis. Warm-up propriu în 20–30 puncte de pornire din istoric, comparații same-bar/same-state cu rularea continuă. Dacă lipsește o condiție, `WAIT`/protecție sigură (nu ordin nou).

**Limita de demonstrație:** oficial Algo API documentează posibilitatea încărcării istoricului, nu garantează aceeași adâncime pe toate instrumentele/conturile sau încărcare instantanee. Modelul final trebuie să fie evaluabil din N bare disponibile și resurse Cloud măsurate, nu dintr-un fișier de antrenare extern.

## 12. Validare anti-overfitting

- Împărțire A/B/C **înghețată înainte de privirea rezultatelor** noii cercetări, cu reguli cronologice și perioade UTC, embargo unde labelurile se suprapun. Nu adapta splitul după P&L. Nicio perioadă deja folosită pentru selecția versiunilor nu este numită „orb” mai târziu.
- A = descoperire și comparații între familii, B = confirmare pentru **ipoteze preregistrate**, C = final **o singură evaluare** după înghețarea completă. Dacă nu există C independentă, nu produce calificare falsă.
- Ledger al **tuturor** ipotezelor, variante, parametri și explorări; ajustare pentru testări multiple; walk-forward cronologic cu capital continuu. Robusteză pe clase/segmente, sensibilitate platou, perturbări orar, eliminare tranzacții de top și bootstrap blocuri cu DD.
- Nu selecta doar cele mai bune instrumente/ore privind B sau C. Ponderea și universul final trebuie definite în A și înghețate pentru B/C.
- **Păstrează minimum 12 luni de confirmare cu adevărat independentă**, conform cerinței OWNER deja existente; nu reeticheta vechi perioade expuse drept independente. Split-ul A/B/C se îngheață înainte de utilizare, iar numărul de observații necesare se verifică statistic, fără scurtarea unilaterală a acestui prag. Screeningul rapid se execută imediat; numai certificarea finală poate necesita timp calendaristic.

## 13. HARD21 și definiția săptămânii eligibile

Săptămână eligibilă = ISO luni 00:00–luni 00:00 UTC, pentru universul PREDECLARAT, cu acoperire necesară de date în sesiunile oficiale și contractele de cost/marjă suficient susținute. Zilele de weekend, sărbători și opririle pieței respectă calendarul oficial. **Nu** declara o săptămână neeligibilă doar pentru că politica are 0 tranzacții, costuri mari sau pierderi. Fiecare săptămână este PASS(≥21 completate financeable), FAIL(<21) sau UNKNOWN(date insuficiente), cu listă concretă a motivelor. Păstrează 300 EUR pe toată evaluarea. Nu forța execuții sau ieșiri pe durată ca să atingi 21.

## 14. Metrici obligatorii, fără câmpuri lipsă cosmetizate

Schema unică ``metrics.json`` per rulare/politică/cost/scenariu, cu: cod+hash date/config+seed, broker/environment/date; capital inițial/final, NET EUR și %, CASH/trivial/random; NET pe săptămână/lună, proporție luni/săptămâni pozitive; expectanță EUR și în multipli de risc, profit factor, win rate, câștig/pierdere medie, streak pierderi, Sharpe/Sortino/Calmar (numai când definite); frecvență completă min/medie/max per săptămână și câte săptămâni au HARD21; durată medie și expunere/correlation; DD equity max/mediu și timpul sub vârf, worst-4w, minimum free margin, evenimente marjă/stop-out, prob. DD>30% la bootstrap; componentă de cost separat și x1/x1,5/x2; pe instrument/clasă/regim/an, top-5 concentration; calibrare estimate vs realizate; explicații intrare/hold/reduce/close și reconciliere/paritate. Fiecare câmp are `status: VERIFIED | MODELED | UNKNOWN | NOT_APPLICABLE` și `source_id`; date lipsă nu devin zero.

Raportul de poartă are maxim **10 rânduri**, în primele 5: NET/CASH, HARD21, DD, date/sursa, verdict; următoarele: cauză eșec, modificări, durata/cheltuieli CI, ce urmează. Registre: `DECISIONS.md`, `RESULTS.md`, `HYPOTHESES.md`; artefactul complet rămâne accesibil și verificabil cu hash.

## 15. Porți obligatorii; fiecare produce un verdict real

| Poartă | Ce se execută efectiv | PASS necesită | La blocaj |
|---|---|---|---|
| **P0: capabilități oficiale + acces** | Matrice API-uri cu **surse oficiale, fără teste Spotware redundante**; inventar cont/surse read-only; contract `as-of`; split/metrici fixate; controale anti-ordine proprii | Capabilități Cloud documentate oficial; acces și date broker verificate numai unde sunt cont-specifice; niciun secret expus | Dacă auth indisponibil: raportează `BLOCKED_SOURCE`; continuă verificările/documentarea fără broker și nu inventa acces |
| **P0.5: diagnostic economic rapid** | Verifică întâi noul artefact autentic #45134137836, refolosește datele valide; completează M15–D1, costuri/mişcări/margini; colectează suplimentar DOAR pentru lipsuri documentate; scenarii; frontiera indicativă HARD21 | Tabel cu surse, date și clasificarea fiecărui instrument/orizont; incompatibilități numai demonstrate | Dacă lipsesc costuri: model pesimist etichetat + intervale, verdict condițional, nu blocaj total |
| **P1: simulator corect** | C# Core și tranzacții contabile manuale; bazelines; anti-lookahead; replay | P&L, FX, margin, swap, DD, gap/fill verificate cu teste, pe surse autentice | Dacă date lipsesc, testare sintetică a motorului și raport explicit `UNKNOWN_ECONOMIC` |
| **P2: descoperire** | Căutare trăsături/regularități în A, preregistrare și multiplicitate | Cel puțin o politică cu NET modelat pozitiv la ×1,5 și finanțabilitate în A **sau raport negativ valid de P2** | Nu rescrie parametrii pe B/C |
| **P3: confirmare** | B înghețat, walk-forward, CASH/trivial/random, ledger 300, HARD21/DD | NET > CASH la ×1,5 și robustețe la ×2, min 21 în fiecare săpt. eligibilă, DD ≤30% în intervalul de scenarii certificat | FAIL/NECONCLUDENT este rezultat, nu invitație la sute de PR-uri |
| **P4: final** | Robusteză, bootstrap blocuri, C neatins exact o dată | Toate criteriile P3 rămân îndeplinite pe C; fără lookahead și selecție retroactivă | Dacă eșuează, ipoteza se închide; nicio a doua încercare pe C |
| **P5: produs** | `.algo` Cloud compatibil, același Core, backtest CLI autentificat pe istoric, paritate de evenimente/ordine/costuri, warm-up 20–30 starturi | Build reproducibil, metadata, parity/fail-safe, proprietarul primește artefactul și instrucțiunile | Dacă CLI credentials lipsesc, `P5 NOT VERIFIED`; nu plasa niciun ordin pentru a „compensa” |

**Interdicția de a lăsa proiectul să se blocheze la P0:** capabilitățile oficiale se ACCEPTĂ DIN DOCUMENTAȚIE, fără probe demonstrative noi. Teste offline numai pentru codul nostru și pentru controalele anti-ordine; colectarea Open API read-only este o capacitate SEPARATĂ de autentificarea CLI. Primul build/metadata se face odată cu primul `.algo` propriu relevant, nu ca experiment izolat pentru funcții Spotware. Backtest-ul autentificat rămâne necesar la P5, când există cBot validabil, însă lipsa acreditărilor CLI nu blochează screeningul P0.5 prin Open API.

## 16. Reguli anti-blocaj și roadmap măsurabil

- **Interzisă cercetarea de tip „Spotware API X oare există?” atunci când pagina oficială atestă direct suport Cloud.** Se citează pagina și se implementează funcția doar dacă servește unei întrebări economice deschise.
- **Un singur issue de roadmap activ și cel mult 4 fluxuri operaționale NOI**, pe cât posibil realizate prin reutilizarea/consolidarea workflow-urilor existente: `verify`, `collect-readonly`, `screen`, `evaluate`. Limita este **prospectivă**: NU trebuie șterse/recreate cele 152 workflow-uri istorice doar pentru a „respecta numărul 4”. Workflow-urile vechi rămân ca dovezi, neautorizate pentru relansări; orice nou job trebuie să aibă o întrebare economică, un buget și o justificare în PR.
- **P0.5 înaintea infrastructurii sofisticate**, conform documentului original; fiecare acțiune trebuie să răspundă unei întrebări de NET/HARD21/DD. Pentru fiecare instrument/protocol: `available data`, `cost completeness`, `fundability`, `scoreable opportunities`, `modeled NET`, `certified NET`.
- **Bugete per job, nu promisiuni de terminare**: `timeout-minutes`, limită memorie dacă platforma permite, volum maxim de cereri, retry/backoff, `concurrency` și `cancel-in-progress` numai pentru joburi de diagnostic, nu pentru originale economice protejate. Run cu estimări intermediare care nu divulgă date; dacă se depășește plafonul, `INCOMPLETE` și cauza, fără timeouts de ore suplimentare prin reîncercări nejustificate.
- **Cel mult 3 încercări tehnice motivate pe același defect de cod/integrare**; această limită NU cere „3 teste” pentru o funcție documentată oficial; dacă nu există progres probat, marchează `BLOCKED`, oferă un traseu sigur alternativ, nu colecta la infinit același eșantion și nu ascunde datele lipsă. Nu face schimbări de model retrospective sub pretextul unui bug.
- Codul cu secrete este rulat NUMAI din `main` revizuit și protejat ori dintr-un SHA înghețat cu control echivalent. PR/push CI fără secrete. Nu descărca și executa cod din fork neîncredere.
- După fiecare rezultat economic, un singur tabel cu `NET vs CASH, HARD21, DD, cost-decomposition, verdict` pe toate alternativele; explicație de abatere față de comparator, inclusiv negativ.
- `P0.5` are ca plafon de proces **10 zile de lucru activ** pentru primul diagnostic. Dacă nu este posibil, se emite raport parțial la poartă, nu un nou ciclu de infrastructură.

## 17. Build, test și paritate cTrader oficiale

- **Toolchain:** `.NET 8` pentru `.algo` conform cerinței actuale CLI [S07], biblioteca `cTrader.Automate` conform ghidului oficial [S18]. Docker CLI oficial, imagine **fixată la digest sau tag identificat și testat**; niciodată `latest` fără înregistrarea digest-ului [S19].
- **Când există implementarea proprie necesară**, secvența fără ordine este `dotnet build` → fișier `.algo` → `ctrader-cli metadata` → teste C# ale propriei logici și simulatorului → `ctrader-cli backtest` pe **istoric** când autentificarea CLI sigură este disponibilă. NU construi `.algo` fictive doar pentru a verifica metode deja documentate oficial. Toolul CLI este **distinct de cTrader Cloud**: un succes CLI nu garantează automat executarea identică în Cloud.
- `backtest` oficial acceptă `open`, `m1`, `m1-csv`, `tick-csv`, `ticks`, rapoarte JSON și costuri explicit configurate [S07]. Paritatea necesită, pe aceeași secvență de piață, decizie/volum/preț/timp/cost/NET al unui cBot nativ vs Core Replay; explicați diferențele de cotare/executare, nu cere „identitate de P&L” pentru două surse cu spread diferit.
- Identificarea pozițiilor proprii este pe etichetă de strategie și ID broker, nu pe fișiere; pozițiile deschise trebuie reintroduse în `HOLD/REDUCE/CLOSE` după restart, nu ignorate sau duplicate [S13].
- Execuția Cloud reală nu se testează în acest mandat pentru că OWNER interzice apăsarea Start; verificarea Cloud este **compatibilitate documentată + build CLI + parity istoric + verificarea operatorului la predare**. Nu scrie „demonstrat live in Cloud” fără test real autorizat.

## 18. Reguli de acceptare și oprire economică

**PASS final** numai dacă `NET > 0` după all-in ×1,5 pe confirmare B și final C, `NET > CASH` și nu depinde exclusiv de un instrument sau de câteva tranzacții, supraviețuiește stresului ×2 conform criteriului preregistrat, `HARD21` în **toate** săptămânile eligibile, DD floating ≤30% și date suficiente pentru certificare, niciun leak temporal, compatibilitate Cloud/CLI dovedită, fără secrete/ordine accidentale.

**FAIL** dacă testele complete infirmă criteriile. **INCONCLUDENT** dacă lipsesc date/istoric sau putere statistică, dar asta nu este `PASS` și nu poate fi schimbat retroactiv. În caz de incompatibilitate demonstrată HARD21 vs NET/DD, Directorul raportează frontiera și propune decizii distincte pentru OWNER, nu relaxează singur standardele.

## 19. Livrabile și disciplina repository-ului PUBLIC

Structură maximă: `data/` (contracte, ingestie), `core/` C#, `sim/` C# runner, `research/` analize/registres, `cbot/` adaptor, `tests/`, `reports/`, `.github/workflows/`. Nimic nu se construiește doar „pentru arhitectură”. Public = cod, schema, rapoarte agregate, hashes de integritate care nu divulgă contul; privat = date reale brute licențiate, secrete și identitate cont. Încheiere la fiecare poartă cu `GATE_Px.md`, `RESULTS.md`, `DECISIONS.md`, `HYPOTHESES.md`; fiecare cu commit SHA, date hash, parametri, perioadă, seed, rezultat, cost și semnătura sursei.

Secretul nu este disponibil automat PR-urilor externe; se controlează environment approvals, accesul contributori și `GITHUB_TOKEN`. Nu este sigur să rulezi cu secrete codul unui PR neîncredere [S16][S17]. **Repository-ul existent, istoricul, artefactele și secretele rămân neșterse și nemutate.** Nu se schimbă setările/protecțiile de branch fără un ordin separat. PR #423 rămâne Draft până la reconcilierea cu `main`; nu se integrează automat.

## 20. Ce face OWNER la final și condiția de activare

După P4+P5, DIRECTOR livrează: `.algo` hash-verificat, versiunea Core, rezumat de performanță **modelată/validată istoric** (nu promisiune), limite broker/Cloud, parametri utilizați, instrucțiuni Android, procedură de oprire, scenarii de avarie. **OWNER este singurul** care încarcă fișierul, selectează contul și apasă Start în cTrader Cloud. Faptul că aplicația poate rula cu telefonul închis [S02] nu garantează profit sau lipsa restartului. Înainte de Start, OWNER verifică pe telefon: cont/monedă/capital, bot și SHA, risc/unități, starea legăturii și butonul Stop.

**Activare V3.2 în proiectul EXISTENT:** OWNER transmite acest document Directorului împreună cu ordinul „CONTINUĂ ÎN ACELAȘI REPOSITORY; FĂRĂ RESTART”. Directorul reconciliază documentul cu starea LIVE, integrează doar ceea ce trece porțile și raportează progresul, fără pauză metodologică artificială. Un eventual repository nou necesită **alt mandat OWNER explicit**, nu rezultă din V3.2.

---

## Anexa A — Matrice: oficial demonstrat vs cont de verificat vs ipoteză

| Afirmație | Dovada | Statut |
|---|---|---|
| Cloud Linux, fără HTTP/fișiere persistente | Spotware [S01] | OFICIAL CONFIRMAT |
| cBot multi-simbol/bar history/volum/marjă/poziții | Spotware [S09][S10][S12][S13] | API OFICIAL CONFIRMAT, NU SE RETESTEAZĂ; cantitatea de date, resursele și codul PROPRIU se verifică |
| OnBarClosed numai după tick-ul următor | Spotware [S11] | OFICIAL CONFIRMAT, NU SE RETESTEAZĂ |
| Token `accounts` doar vizualizare, `trading` poate transmite ordine | Spotware [S05] | OFICIAL CONFIRMAT, NU SE RETESTEAZĂ; protecția COLECTORULUI propriu SE TESTEAZĂ |
| Live Open API pentru date, endpoint separat de demo | Spotware [S04][S06] | OFICIAL CONFIRMAT, NU SE RETESTEAZĂ; accesul contului REAL trebuie verificat |
| Bar/tick depth exact Pepperstone pentru fiecare simbol | Nu există probă din documentația generică | DE MĂSURAT CU CONTUL |
| Comisioane, spread, swap, conversie, marjă istorice individuale | Pepperstone [S15] descrie familii, nu trasee individuale | CONT-SPECIFIC/ESTIMĂRI ETICHETATE |
| Fills de backtest = fills reale în Cloud | Nicio garanție Spotware | NU SE AFIRMĂ; se validează doar paritatea limitată de sursa istorică |
| Spotware API disponibil = cBot nostru verificat/validat | Documentația API certifică funcția, nu implementarea noastră | **NU**; teste doar codul nostru, nu platforma |
| R:R bun elimină costurile | Nu este o lege economică | FALS CA GARANȚIE, DE TESTAT NET |
| 300 EUR, HARD21, DD ≤30%, NET pozitiv | Condiții OWNER, nu funcții ale API-ului | CRITERII ÎNGHEȚATE, NU REZULTATE |

## Anexa B — Surse oficiale utilizate (consultate 23.11.2026)

- **[S01] Spotware Cloud requirements:** https://help.ctrader.com/ctrader-algo/documentation/cbots/cloud-requirements/
- **[S02] Spotware Cloud features:** https://help.ctrader.com/ctrader-algo/documentation/cloud-features/
- **[S03] Spotware cBots introduction:** https://help.ctrader.com/ctrader-algo/documentation/cbots/
- **[S04] Spotware Open API overview, rate limits, LIVE:** https://help.ctrader.com/open-api/
- **[S05] Spotware OAuth scopes:** https://help.ctrader.com/open-api/account-authentication/
- **[S06] Spotware endpoints LIVE/DEMO:** https://help.ctrader.com/open-api/proxies-endpoints/
- **[S07] Spotware CLI backtesting and .NET 8:** https://help.ctrader.com/ctrader-cli/cbots/
- **[S08] Spotware CLI FAQ credentials:** https://help.ctrader.com/ctrader-cli/faq/
- **[S09] Spotware MarketData/GetBars:** https://help.ctrader.com/ctrader-algo/references/MarketData/MarketData/
- **[S10] Spotware Bars/LoadMoreHistory:** https://help.ctrader.com/ctrader-algo/references/MarketData/Bars/Bars/
- **[S11] Spotware BarClosed semantics:** https://help.ctrader.com/ctrader-algo/documentation/cbots/cbot-bar-events/
- **[S12] Spotware Symbol/min-volume/estimated-margin:** https://help.ctrader.com/ctrader-algo/references/MarketData/Symbols/Symbol/
- **[S13] Spotware Positions.FindAll:** https://help.ctrader.com/ctrader-algo/references/Trading/Positions/Positions/
- **[S14] Spotware historical ticks/trendbars:** https://help.ctrader.com/open-api/symbol-data/
- **[S15] Pepperstone official costs and fees:** https://pepperstone.com/en/trading/costs-and-fees
- **[S16] GitHub Secrets:** https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
- **[S17] GitHub Secure use:** https://docs.github.com/en/actions/reference/security/secure-use
- **[S18] Spotware official IDE/NuGet:** https://help.ctrader.com/ctrader-algo/visual-studio-ides/
- **[S19] Spotware official CLI Docker:** https://github.com/spotware/ctrader-console-docker
- **[S20] Spotware Algo fault tolerance:** https://help.ctrader.com/ctrader-algo/documentation/fault-tolerance/
- **[S21] Spotware Algo rate limits:** https://help.ctrader.com/ctrader-algo/documentation/rate-limits/

*Notă despre exactitate:* documentația Spotware și Pepperstone poate evolua. Executantul **citează versiunea/documentația curentă** pentru capabilități, fără a relua teste demonstrative ale acestora; confirmă doar integrarea proprie, versiunea pachetului la build și observațiile contului. Acest mandat nu autorizează nicio tranzacție.*