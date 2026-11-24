# Protocol prospectiv pentru portofoliul cu rezervă de finanțare

Data preregistrării este 24 noiembrie 2026. Obiectul evaluării este utilizarea unei rezerve de finanțare acoperite documentar în același motor C# care emite LONG, SHORT, WAIT, HOLD, REDUCE și CLOSE. Execuția nouă are nevoie de o identitate și de o fereastră distincte. Rezultatele CPE1 oferă diagnosticul tehnic al întreruperii.

## Ipoteză și comparatori

Ipoteza este că, atunci când un debit de finanțare încă nedecontat este plafonat prin dovadă verificată, motorul poate aloca din capitalul rămas și poate închide repetat oportunități cu NET advers incremental pozitiv față de WAIT/CASH. Ipoteza este infirmată dacă activitatea redevine posibilă, dar randamentul advers, frecvența sistemică sau drawdown-ul eșuează. Folosirea unei rezerve poate reduce numărul oportunităților eligibile.

Programul compară trei registre exclusive, fiecare cu 300 EUR și fără resetări. Politica economică aplică aceeași evaluare cauzală în EUR la selecție și la gestionarea expunerii. Controlul SIMPLE ia prima geometrie legal finanțabilă, cu stopul structural și ținta observată definite la intrare. CASH păstrează cei 300 EUR. Toate registrele folosesc aceleași contracte, termene cunoscute la momentul deciziei, furnizor de evidență și trasee de observație. Pentru atribuirea HOLD/CLOSE se publică separat intrările comune după simbol, direcție, semnal, volum și ceas de fill. Diferența integrală dintre politici include și selecția.

Semnalele provin exclusiv din bare M5 și M15 închise înaintea deciziei. Intențiile și execuțiile modelate au ceasuri distincte. Volumul rămâne pe grila originală. Ieșirea normală este structurală sau economică, cu protecția de capital în vigoare. Dovada scadentă pentru finanțarea deja acumulată este procesată înaintea unei intrări. O ofertă de finanțare trebuie să acopere expunerea până la următorul ceas M5 la care calendarul verificat permite gestionarea poziției, inclusiv după o întrerupere programată. Dovada se verifică din nou la fill și la următoarele decizii economice de gestionare.

## Evidență financiară necesară

Fiecare dovadă trebuie legată de furnizor, cont, instrument exact, sens, volum, monedă EUR, interval efectiv și momentul disponibilității. Se acceptă numai valoarea semnată a finanțării exacte ori o limită verificabilă a debitului total. Tariful prezent, OHLC și un hash de format valid sunt insuficiente pentru autentificarea unei limite istorice. Adaptorul de sursă are responsabilitatea autentificării și a reconcilierii intervalului înainte de a emite dovada tipizată.

Capitalul demonstrabil folosește soldul contabil, lichidarea observată, marja pozițiilor Held, rezervarea Pending OPEN și plafonul suplimentar de debit al tuturor ferestrelor de finanțare. O poziție care primește REQUEST_CLOSE rămâne Held până la un CLOSE_FILL ulterior. Când un plafon lipsește, capitalul finanțabil este necunoscut, detectorul continuă, iar gestionarea și ieșirea protectivă rămân active. Înregistrarea unui plafon disponibil după închidere afectează rezerva la ceasul când dovada devine disponibilă. NET-ul rămâne necunoscut cât timp registrul păstrează o diferență de finanțare nedecontată.

## Fereastră și verdict

Confirmarea va folosi cel puțin 53 de săptămâni ISO complete și consecutive, începând cu prima zi de luni la 00:00 UTC după înregistrarea implementării de evaluare și a surselor autentice eligibile. Săptămânile eligibile se stabilesc din calendarul brokerului și acoperirea sursei, înaintea rezultatelor. Săptămânile calendaristice, săptămânile cu detector activ, eligibilitatea financiară și numărul de tranzacții complete se publică distinct. Niciun segment expus CPE1 nu participă la confirmare. Niciun simbol sau multiplicator nu se alege din clasamentul CPE1.

Rezultatul solicită NET complet reconciliat, câștig advers incremental față de CASH, continuitate pe fereastra independentă, HARD21 la nivel de sistem în fiecare săptămână eligibilă și drawdown maxim de 30%, inclusiv pozițiile deschise. Scenariile de cost 1×, 1,5× și 2× se raportează integral, cu finanțarea contabilizată separat de celelalte costuri. Profitul estimat fără limite de finanțare sau cu traseu de equity incomplet se publică drept provizoriu. Analiza de concentrație raportează contribuția pe instrument, zi și episod fără a transforma performanța unui subset în verdict.

Etapa curentă verifică proveniența și paritatea tehnică. Pornirea economică necesită dovadă autentică pentru stările de finanțare, paritate la fiecare eveniment și documentarea acoperirii riscului flotant. Această versiune are zero ordine LIVE sau DEMO și zero activări Cloud.
