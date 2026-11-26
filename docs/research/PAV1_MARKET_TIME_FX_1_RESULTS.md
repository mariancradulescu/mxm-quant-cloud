# PAV1_MARKET_TIME_FX_1 — rezultate originale și limite

Mandatul OWNER după PR507–511. Selecția cronologică înghețată la 16 noiembrie este **WAIT**. Nicio configurație nu este calificată sau promovată. Datele sunt deja expuse proiectului; această dezvoltare nu reprezintă confirmare independentă pe 12 luni.

## Rezultatul monetar

Cele 45 de portofolii comune includ 39 de configurații/scenarii și șase controale CASH. NET-ul închis este determinabil în 37/39: 29 pozitive, opt negative; două rămân nedeterminate. CASH rămâne 300 EUR. Fiecare portofoliu începe cu 300 EUR pentru întregul univers, fără resetare la 16 noiembrie. Toate rezultatele de mai jos sunt scenarii istorice condiționale, nu decontări certificate de broker.

| Configurație | NET închis S0 / S1 / S2, EUR | Rezultat suplimentar |
|---|---:|---|
| MT25_CLOCK | +61.460341 / +36.467562 / +15.985471 | 495 / 398 / 333 închideri; HARD21 în toate cele trei săptămâni complete |
| MT25_CONSENSUS | +17.412912 / +15.713965 / +21.811334 | Portofolii complet închise; HARD21; W47 negativ în toate scenariile |
| MT25_GAP_RESERVE | +48.076184 / +34.794445 / +9.059397 | Reduce depășirile rezervei; nu demonstrează recurență robustă |
| MT25_H1_72 | -0.962298 / +0.199410 / +6.629523 | W47 pozitiv, însă rezultatul integral și frecvența nu sunt robuste |
| MT25_CAPTURE_M5 | -23.013380 / -46.043214 / -55.250825 | Frecvența mai mare produce rezultate mai slabe |

CLOCK încheie cu 3 / 2 / 2 poziții deschise. Creșterea equity condiționale, după evaluarea lor și finanțarea modelată, este **+60.464933 / +35.157954 / +14.680435 EUR**. Aceste valori nu sunt NET realizat al unui portofoliu complet închis. DD eșantionat: 15.5668% / 16.1370% / 15.2074%; nu se certifică DD intrabar continuu.

CLOCK W47: +10,743842 / +8,396364 / +0,824405 EUR. **W46 rămâne negativ: −4,142720 / −5,678838 / −2,120758 EUR.** Îmbunătățirea W47 nu rezolvă recurența. Scorul de selecție, calculat numai din stările salvate înaintea perioadei ulterioare, este negativ; rezultatul ulterior nu înlocuiește selecția.

Extinderea RISK_CONTROL de la 21 la 25 de instrumente introduce două închideri USDJPY în S0, ambele negative, cu total −1,788585 EUR. În CLOCK S0, cele cinci închideri USDJPY totalizează −4,811385 EUR. Extinderea universului este implementată economic; numărul de instrumente nu dovedește avantaj.

## Conversia și obligațiile financiare

Metoda strictă originală de 120 minute rămâne păstrată. Scenariul separat folosește ultimul curs autentic în perioade închise confirmate de calendar și măsoară vechimea în timpul deschis, cu plafon de patru zile calendaristice. Pentru răspunsurile recuperate, 1.445 / 2.885 minute calendaristice înseamnă cinci minute deschise. Nu se modifică timestampul observației originale și nu se inventează rate. Pentru conversii de execuție pe piețe deschise rămâne limita originală de 30 secunde; evaluările condiționale ale deținerilor nu intră în semnale/fill/stop.

Cele 18 răspunsuri existente rezolvă condițional toate cele zece registre ETHUSD închise din original, fără reluarea vreunei decizii. CLOCK original complet închis: **+36,717772 / +29,342470 / +17,050448 EUR**. RISK_CONTROL S0: +12,393565 EUR; S1/S2 originale determinate rămân +20,803990 / +23,521171 EUR. Nicio equity necunoscută originală nu este restaurată retrospectiv, iar originalul strict S0 rămâne nedeterminat.

În noul studiu rămâne o obligație nouă în MT25_H1_24 S0: AAPL.US SHORT 0,1 unități, deschis 2 noiembrie, închis 3 noiembrie. Lipsește BID-ul autentic necesar la taxa din 2 noiembrie 22:00 UTC; cursul EURUSD și tariful sunt disponibile. Nu este un blocaj de autentificare și nu se înlocuiește suma necunoscută cu zero. Celelalte configurații experimentale au NET închis determinat; pozițiile/intentiile rămase la final sunt raportate separat.

## Riscul ulterior, volumul și gestionarea

**Zero creșteri ale riscului rezervat la fill** în toate cele 39 de configurații/scenarii. Acest control nu este echivalent cu limitarea garantată a pierderii ulterioare.

CLOCK depășește ulterior rezerva în 134 / 112 / 99 episoade, cu exces total 10,790728 / 13,969400 / 20,507175 EUR. Exemplu AMD.US S0: rezervă la fill 0,762064 EUR, pierdere NET 2,473190 EUR, exces 1,711127 EUR; cotația de execuție este la 18,50 unități de preț dincolo de stop. Exemplu GBPUSD S2: rezervă 0,884770 EUR, pierdere 3,817826 EUR; distanță dincolo de stop 0,00154 și slippage modelat 0,00170. În aceste cazuri există dovezi native ale gapului, mișcării după trigger și/sau creșterii costului la execuție. Acoperirea necunoscută a altor intervale nu este eliminată prin aceste exemple.

Rezerva bazată pe gapurile H1 observate păstrează stopul și destinația. Reduce numărul depășirilor la 2 / 6 / 10 și excesul la 0,549463 / 1,984429 / 6,652494 EUR. Nu garantează riscul și nu este declarată succes economic: W47 devine negativ în S1/S2 și profitul total este inferior CLOCK.

Optimizarea volumului condiționată de rezultate monetare proprii mature produce exact același lanț de evenimente ca alocarea la volumul minim în toate cele trei scenarii. Suportul suplimentar nu justifică volume mai mari; avantajul lor economic nu este demonstrat. Cerințele de minimum 20 episoade, trei zile și penalizarea de incertitudine rămân neschimbate. Absența suportului pentru volum suplimentar păstrează intrarea minimă eligibilă.

Gestionarea M5 închide 953 / 730 / 601 episoade, dar NET-ul este negativ în toate scenariile. Numărul de tranzacții nu este tratat drept îmbunătățire monetară.

## Universul și conservarea

25 de instrumente sunt evaluate; cele patru adăugate anterior folosesc exclusiv cotațiile autentice disponibile la 23–25 noiembrie. O tranșă nouă adaugă USDX, XPDUSD, Copper și DOTUSD: univers colectat 29. Sunt verificate **2.111.628 bare**, cu date efective care ating peste 12 luni pe toate cele șapte intervale pentru fiecare instrument. Două bare H4 și două D1 DOTUSD au intervale nominale suprapuse: toate se păstrează brut și sunt excluse explicit din contextul reutilizabil. Nu se presupun alte ore de închidere. Un an de bare nu certifică un an de rezultate economice, tarife istorice sau continuitate completă.

Sursele normalizate sunt conservate criptat, cu manifest verificabil și fragmente de maximum 32 MiB. Originalele brute, rezultatele și selecția nu sunt rescrise. Finalizarea tehnică reconstruiește exclusiv sursa pentru identitate și conservare; nu execută din nou politici economice.

## Dovezi GitHub

- Studiu economic original: [45835675932](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/45835675932), artefact **15126531887**, SHA-256 `61449060de450d61f01652bae012a66ef6d187fbc078b97046562ff619db06b5`.
- Protocol înregistrat neschimbat: `5c3639991f6292b887c416115d17e70c2f4d308f15168610b3f6d3c8bee19045`.
- Execuția economică a publicat toate cele 45 rezultate; starea finală FAILURE provine din manifestul public de custodie suprascris de un artefact vechi. Integrarea recipientului curent într-un director separat corectează cauza. Rezultatele sunt conservate byte-identic în recuperarea finală **SUCCESS** [45837796648](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/45837796648).
- Arhiva finală recuperată: **15125604551**, SHA-256 `e7075bbfbe0769a03a0b9f28a3aec0f66f0f87335699573b60e4ef1da065f768`. Cache al sursei identice: **15125624461**, 130 fișiere, SHA-256 `455d204b97c1df36908d55e905aaa893b66d0e12dadbdfb2114201334bed4b9b`.
- Colectare nouă: [45829391256](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/45829391256), rezumat 15122428422, SHA-256 `13742ca539dc994f7228da3ec44aafe6ca5fd75723a75e6783d460cdf5a658aa`.
- Verificarea intervalelor reale: [45835675987](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/45835675987), artefact public **15125780700**, SHA-256 `013ec18ecc163d7f1a50b10fc601733184138344324eba592c728e651be15d59`.
- Cache normalizat al tranșei noi: 15125391357, SHA-256 `31bf99af7a8c22d3eaf72ca0efb5d0824b55c22b3b4341ef247877a2f53e871b`, criptat, fără politici executate.

Zero ordine LIVE/DEMO. Zero activări Cloud. Zero promovări necertificate.
