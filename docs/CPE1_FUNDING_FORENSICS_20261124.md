# CPE1 după recuperare

**Verdictul economic rămâne fără calificare.** Prima evaluare a finanțării necunoscute a închis admiterile ECONOMIC după 662 de detecții. Alte 155.285 de detecții au avut loc ulterior în fiecare registru ECONOMIC. CPE1 a parcurs 74.238 de ceasuri M5 în 52 de săptămâni calendaristice. Pentru oportunitățile ulterioare a lipsit o evaluare financiară individuală.

Originalul este execuția #45370323302, artefact #14909305890, la commitul `8018251119223cfaa00d94fda513a43e2616de27`. SHA‑256 al ZIP-ului original este `f23fb4616f044086b130343cc8a52adeb20bdbe82c9976020208d71e7d1e8318`. Recitirea surselor a folosit aceleași cinci arhive autentificate, ambele fișiere originale verificate după hash și detectorul C# original. A reconciliat totalurile de detecții și toate verificările de finanțare necunoscută. Numărul de politici economice executate în această recitire este zero. [Execuția originală](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/45370323302/artifacts/14909305890) · [Recitirea surselor](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/45376822819/artifacts/14911512496) · [Raportul JSON original al recitirii](evidence/cpe1-funding-source-audit-14911512496.json)

## Prima finanțare necunoscută

Orele din tabel sunt UTC. Pe 17 și 24 noiembrie 2025, ora 23:00 UTC corespunde orei 01:00 din ziua următoare în România. US500 și NAS100 au fost simultan afectate în registrele ECONOMIC 1,5× și 2× la rezoluția ceasului observat. Pentru fiecare poziție afectată, volumul modelat era 0,1 unități.

| Registru | Primul ceas blocat în 2025 | Poziție afectată | Ultimul CLOSE_FILL UTC | Detecții înainte | La blocare | După blocare | După Held=Pending=0 |
|---|---|---|---|---:|---:|---:|---:|
| ECONOMIC 1× | 17 nov. 23:00 | US500 LONG | 18 nov. 00:25 | 662 | 0 | 155.285 | 155.262 |
| ECONOMIC 1,5× | 17 nov. 23:00 | US500 SHORT și NAS100 LONG | 17 nov. 23:55 | 662 | 0 | 155.285 | 155.269 |
| ECONOMIC 2× | 17 nov. 23:00 | US500 SHORT și NAS100 LONG | 17 nov. 23:55 | 662 | 0 | 155.285 | 155.269 |
| SIMPLE 1× | 24 nov. 23:00 | US500 LONG | 25 nov. 09:00 | 3.824 | 1 | 152.122 | 151.849 |
| SIMPLE 1,5× | 24 nov. 23:00 | US500 LONG | 25 nov. 09:00 | 3.824 | 1 | 152.122 | 151.849 |
| SIMPLE 2× | 17 nov. 23:00 | US500 LONG | 18 nov. 03:40 | 662 | 0 | 155.285 | 155.171 |
| CASH 1×, 1,5× și 2× | Fără incident | Fără expunere | — | 155.947 pe întreaga fereastră în fiecare registru | — | — | — |

Ceasurile Unix exacte sunt `1763420400000` și `1764025200000` milisecunde. Primul cadru eligibil pentru verificarea poziției după ceasul modelat de swap de 22:00 UTC a fost la 23:00 UTC. Finanțarea este verificată înainte de orice OPEN_FILL al unei intenții restante. Rezultatul necunoscut setează `cpe1UnreconciledFunding`. `Cpe1RecheckFill` respinge următorul fill al unei intenții active, iar `AdvanceCpe1` sare peste evaluarea fiecărei oferte ulterioare. Detecția rămâne activă. Închiderea reduce expunerea și eliberează marja la CLOSE_FILL. Indicatorul global rămâne activ și după închiderea ultimei poziții.

Numărul admiterilor demonstrate după blocare este zero. Eligibilitatea financiară efectivă și numărul refuzurilor datorate **exclusiv** indicatorului rămân necunoscute. Registrul original a oprit verificarea geometriei, marjei, riscului și comparației economice, iar plafonul debitelor nedecontate lipsește. Aceste detecții pot include același simbol sau același interval. Totalurile sunt per registru și nu se însumează ca oportunități unice sau tranzacții realizabile. Sursa nu conține payoff-uri ulterioare pentru tranzacții neexecutate de original.

## Ce s-a recuperat din contracte

Cele două CFD-uri cash sunt NAS100, `symbolId=126`, și US500, `symbolId=127`, cotate în USD. AIP1 #41735441128 conservă răspunsurile `ProtoOASymbolByIdRes` din care provin termenele folosite de CPE1, marcate 2 noiembrie 2026 00:00 UTC în banda originală. HXC1 #43817213663, XMH2 #44352570167 și loturile de contracte P05 #45134137836 conservă capturi autentificate suplimentare din 2026. Lista publică a celor 48 de piețe P05 nu include indicii respectivi. Contractele lor există în loturile brute P05. BDP1 #41724643418 păstrează răspunsurile FX, inclusiv AUDUSD, EURUSD și GBPUSD. [Recitirea câmpurilor din cele cinci arhive](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/45376822819/artifacts/14911512496)

| Câmp | AIP1 pentru ambii indici | În motorul CPE1 original |
|---|---|---|
| `swapCalculationType` | 1, procent anual | 1. Funcția de finanțare acceptă numai 0, PIPS |
| `swapLong`, `swapShort` | −6,41 și +1,41 | Păstrate. Celelalte trei capturi au −6,42 și +1,42 |
| `swapPeriod`, `swapTime` | 24 ore, 1320 minute UTC | Păstrate |
| `swapRollover3Days` | 5, vineri | `null` |
| `chargeSwapAtWeekends`, `skipSWAPPeriods` | `false` și 0, explicite | `null` și `null` |
| `pipPosition`, `scheduleTimeZone` | 0 și `America/New_York` | Poziția pipului s-a păstrat. Ceasul swap folosește minutul UTC din câmpul dedicat |

Au existat **două defecte de implementare**. Adaptorul anual a lăsat în afara benzii trei câmpuri și completarea BDP1 nu le-a restaurat pentru indicii din AIP1. În plus, funcția de finanțare refuză tipul procentual chiar dacă toate câmpurile celelalte sunt disponibile. Spotware documentează tipul 1 ca procent anual și `swapTime` ca minut UTC. [Modelul Open API Spotware](https://help.ctrader.com/open-api/model-messages/#protooaswapcalculationtype)

Obligația rămasă este finanțarea semnată în EUR pentru fiecare interval traversat de cele opt poziții afectate, la dimensiunea, sensul și termenii contului respectiv. Există bare, volume și capturi de tarif din 2026. Lipsește tariful efectiv sau o limită documentată pentru 17 și 24 noiembrie 2025. Aceasta trebuie să includă calendarul exact pentru contract și cont, baza de preț pentru calcul, rata pe sens, convenția de calcul și ruta/conversia USD–EUR cu rotunjire. Spotware indică un divizor 365 pentru formula publică a serverului pentru swap procentual. Documentul general Pepperstone pentru index CFD arată 360. Niciuna dintre publicații nu leagă rata aplicabilă de pozițiile și zilele din original. Un extras broker poate certifica un swap executat efectiv pentru o tranzacție identificată. Pentru poziții modelate este necesară seria tarifară aplicabilă sau un plafon atestat, împreună cu valorile de referință. [Spotware](https://help.ctrader.com/plugins/developers/all-apps/sdk-references/public-server-model/#protoswapcalculationtype) · [Pepperstone](https://pepperstone.com/en/markets/indices/index-fees) · [Câmpurile unui deal cTrader](https://help.ctrader.com/open-api/model-messages/#protooaclosepositiondetail)

După închidere, menținerea datoriei separate este justificată economic. Interdicția permanentă, independentă de o dovadă ulterioară validă, este excesivă. Pentru registrele CPE1 închise, în lipsa oricărui plafon verificat, suspendarea intrărilor rămâne justificată. Marja eliberată și soldul provizoriu nu demonstrează capitalul disponibil.

## Rezultatul conservat și distribuția episoadelor

NET provizoriu include costurile modelate cunoscute și exclude finanțarea istorică nerezolvată. Medianele R net provin doar din episoadele care au un R net publicat de original. R:R este geometria la fill, iar DD este eșantionat pe sursa disponibilă. Valorile HARD21 de mai jos sunt pur descriptive din numărul brut al închiderilor modelate.

| Registru | Brut € | NET provizoriu € | Câștiguri/pierderi nete provizorii | R:R median | R brut median | R net median | Durată mediană | DD eșantionat | Săpt. cu ≥21 închideri |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ECONOMIC 1× | −4,6595 | −7,2876 | 7/18 | 1,20 | −0,67 | −0,81 | 60 min | 4,55% | 1/52 |
| ECONOMIC 1,5× | +22,1232 | +14,8911 | 9/24 | 1,17 | −0,62 | −0,73 | 40 min | 4,76% | 1/52 |
| ECONOMIC 2× | +19,9860 | +9,9520 | 9/24 | 1,04 | −0,60 | −0,74 | 40 min | 5,12% | 1/52 |
| SIMPLE 1× | −29,0398 | −47,6436 | 67/114 | 0,95 | −0,59 | −0,75 | 55 min | 16,49% | 2/52 |
| SIMPLE 1,5× | −43,8491 | −69,7806 | 60/108 | 0,76 | −0,55 | −0,77 | 57,5 min | 23,72% | 2/52 |
| SIMPLE 2× | −5,3998 | −10,8877 | 13/16 | 0,71 | −0,42 | −0,38 | 55 min | 4,05% | 1/52 |
| CASH, toate costurile | 0 | 0 | 0/0 | — | — | — | — | 0% | 0/52 |

În ECONOMIC 1,5×, câștigurile provizorii însumează +42,79 EUR și pierderile −27,90 EUR. Un singur episod a avut R net +62,50, iar mediana celor 31 de valori publicate este −0,73 R. NAS100 are +28,42 EUR în zece episoade. Celelalte patru instrumente au −13,53 EUR cumulat. Cele mai bune patru episoade NAS100 însumează +36,70 EUR. În 16 noiembrie s-au închis două episoade, cu −1,30 EUR provizoriu. În 17 noiembrie s-au închis celelalte 31, cu +16,19 EUR. La 2×, cele mai bune patru episoade NAS100 însumează +36,14 EUR, iar NAS100 totalizează +24,16 EUR. Varianta 1× rămâne negativă, cu episoade în 16, 17 și 18 noiembrie UTC.

Compararea intrărilor după instrument, familie, sens și ceasul deciziei arată selecții diferite. ECONOMIC 1× împarte 13 intrări cu 1,5× și tot 13 cu 2×. ECONOMIC 1,5× și 2× împart 32 dintre cele 33 de intrări, cu fill și închidere la același ceas pentru toate cele 32. SIMPLE 1× și 1,5× împart 129 de intrări din 181 și 168. SIMPLE 2× împarte 19 cu 1× și 28 cu 1,5×, din 29 de închideri. Diferența brută între stresuri include intrări diferite și, pentru SIMPLE, o dată diferită de blocare.

| Cost | Intrări ECONOMIC și SIMPLE comparabile | Diferență de ceas de close | NET provizoriu ECONOMIC minus SIMPLE pentru perechi |
|---|---:|---:|---:|
| 1× | 8 | 1 | −1,6800 EUR |
| 1,5× | 8 | 2 | −1,7061 EUR |
| 2× | 8 | 2 | −1,7062 EUR |

Perechile au același sens, volum și ceas de fill, cu NET condițional și fără gap în ambele politici. Diferența se concentrează pe un US500 închis la 00:40 de ECONOMIC și la 00:25 de SIMPLE, pe 17 noiembrie. În ECONOMIC 1,5×, ieșirile au fost 15 stopuri structurale, nouă invalidări M15, opt eșecuri de continuare după atingerea obiectivului și o decizie de continuare sub CASH. Cele opt eșecuri de continuare după atingerea obiectivului însumează +41,77 EUR provizoriu. Acestea arată contribuția contabilă a clasei de ieșire în propriul registru. Diferența față de SIMPLE include selecția și durata de funcționare. Niciun episod original nu are reducere parțială. Duratele ECONOMIC au fost între 10 și 475 de minute.

Chiar înainte de blocare, istoricul ECONOMIC utilizabil pentru RANGE_TRANSITION era de 19 episoade la 1× și 21 la 1,5× și 2×, în toate cazurile pe două zile UTC. EQUILIBRIUM_REPAIR avea 4, 10 și 10 episoade, pe o singură zi UTC. Funcția înghețată cere minimum 20 de episoade și trei zile de închideri pentru limita inferioară a randamentului brut. Niciuna dintre familii nu a atins împreună condițiile înaintea suspendării.

## Corecția aplicată în Core

Motorul comun primește prospectiv evidență legată de poziție, volum, interval și ceasul disponibilității. Folosește același registru finanțat pentru decontarea sumelor dovedite. Când există doar un plafon, îl reține ca rezervă până la reconciliere și calculează capitalul eligibil după Held și Pending OPEN. O dovadă nouă poate da o limită unei datorii deja închise, cu reluarea admiterii numai dacă trec verificările de marjă, stop, cost și drawdown. Lipsa limitei păstrează capitalul eligibil necunoscut și permite în continuare gestionarea pozițiilor și detecția.

Tipurile de evidență și verificările de cauzalitate sunt implementate. Identitatea sursei și calculul exact pentru un contract procentual la o dată istorică rămân responsabilitatea adaptorului autentificat. Dovada de tarif sau plafon pentru CPE1 nu există în sursele recuperate. Verificarea tehnică folosește cadre identice în Core și adaptorul Cloud de observație, dovadă înainte și după close, reluare din checkpoint și reconcilierea faptelor în registru. DD astfel calculat este eșantionat și conservator față de soldul modelat. Atestarea DD continuu are nevoie și de traseul complet al equity. [Protocolul preregistrat](../research/PROSPECTIVE_FINANCING_RESERVE_PROTOCOL_20261124.md)
