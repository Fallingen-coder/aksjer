# Handelskunnskapsbase — AI-aksjemegler

Dette dokumentet brukes av analyse-scriptet som systemprompt-kontekst
for å ta bedre beslutninger om kjøp, salg og hold.

---

## 1. Tekniske indikatorer

### RSI (Relative Strength Index)
- Måler fart og styrke på kursendringer, skala 0–100
- **RSI < 30** → oversolgt, potensielt kjøpssignal (mulig bounce)
- **RSI > 70** → overkjøpt, potensielt salgssignal (mulig korreksjon)
- RSI alene er ikke nok — bruk alltid bekreftelse fra volum eller MACD
- I sterk trend kan RSI forbli overkjøpt/oversolgt lenge — ikke selg blindt

### MACD (Moving Average Convergence Divergence)
- Viser forholdet mellom to eksponensielle glidende gjennomsnitt (12 og 26 perioder)
- **MACD-linje krysser over signallinje** → bullish, kjøpssignal
- **MACD-linje krysser under signallinje** → bearish, salgssignal
- MACD er en etterslepende indikator — kombinér med RSI for bekreftelse
- Regelen: ta aldri en handel med mindre MACD og RSI er enige

### Glidende gjennomsnitt (MA / EMA)
- EMA (eksponentielt) gir mer vekt til ferske priser enn SMA
- **EMA 9 krysser over EMA 21** → kortsiktig bullish momentum
- **Kurs over EMA 50** → overordnet opptrend
- **Kurs under EMA 50** → overordnet nedtrend
- Støtte/motstand: kursen returnerer ofte til MA-nivåer

### VWAP (Volume Weighted Average Price)
- Gjennomsnittspris vektet med volum — brukes mye av institusjonelle aktører
- **Kurs over VWAP** → institusjonelle kjøpere er i kontroll, bullish
- **Kurs under VWAP** → selgersiden dominerer, bearish
- Sterkt signal ved åpning av børsdagen

---

## 2. Volumanalyse

Volum er det viktigste bekreftelsessignalet. Pris uten volum lyver.

### Gyldige kjøpssignaler (høy konfidens)
- Breakout over motstand med volum **minst 1,5x–2x** snittet → institusjonelt kjøp
- Volumtopp etterfulgt av kursstabilisering → panikksalg over, "washout"
- Stigende kurs med stigende volum → sterk trend, momentum-kjøp
- Pris over VWAP med stigende volum → institusjonelle kjøpere

### Falske signaler (lav konfidens — unngå)
- Breakout på *lavere* volum enn snittet → sannsynlig falsk breakout
- Kursfall på lavt volum → svak selging, ikke nødvendigvis trend
- Volumspike uten retningsklar kursreaksjon → usikkerhet

### Institusjonell akkumulering
Institusjonelle aktører sprer kjøp over dager/uker. Tegn:
- Gradvis stigende kurs med jevnt høyt volum
- Kurs holder støttenivå gjentatte ganger med kjøpsvolum
- Liten kursreaksjon nedover tross dårlige nyheter

---

## 3. Støtte og motstand

- **Støtte**: Prisnivå der kjøperne historisk har kommet inn
- **Motstand**: Prisnivå der selgerne historisk har tatt gevinst
- Brutt motstand blir ny støtte (og omvendt)
- Jo flere ganger et nivå er testet, desto sterkere er det
- **Fibonacci retracements** (23,6%, 38,2%, 61,8%) er naturlige støtte/motstandsnivåer

---

## 4. Nyhetssensitivitet

Nyheter kan overstyre all teknisk analyse.

### Positiv kursreaksjon sannsynlig
- Inntjening over forventning (earnings beat)
- Ny stor kontrakt eller avtale
- Oppkjøp til premie over markedspris
- Analyst-oppgradering (Buy/Outperform)
- Sentralbank senker renter (positivt for vekstaksjer)

### Negativ kursreaksjon sannsynlig
- Inntjening under forventning (earnings miss)
- Nedjustering av guidens
- Regulatorisk bot eller juridiske problemer
- CEO-avgang uten tydelig etterfølger
- Analyst-nedgradering (Sell/Underperform)

### Sentimentregler
- Sentiment spikes (mange negative nyheter på én gang) forutser store kurssvingninger
- Markedet er *fremadskuende*: ca. 45–50% av kursvariasjonen forklares av forventninger
- Ikke overreager på én nyhet — vurder den i kontekst av trend og volum
- Unngå kjøp rett før kjente risikohendelser (rentebeslutninger, kvartalstall)

---

## 5. Risikostyring (KRITISK)

### Posisjonsstørrelse
- Risikoregelen: **aldri risikér mer enn 1–2% av total porteføljeverdi per handel**
- Konsistente posisjonsstørrelser (ikke la følelser bestemme størrelsen)
- 85% av tradere som holder seg til 1–2%-regelen er aktive etter 2 år
- 88% av tradere som risikerer 10%+ per handel taper hele kontoen innen 1 år

### Stop-loss
- Stop-loss beskytter *kontoen*, ikke bare én handel
- Plassér stop strategisk — ved teknisk nivå (siste lavpunkt, MA-støtte), ikke tilfeldig
- En god stop-loss er 1,5x–2x ATR (gjennomsnittlig dagsvolatilitet) under inngangspris
- Aldri fjern en stop-loss etter at prisen har beveget seg mot deg

### Take-profit
- Best praksis: **2R–3R mål** (ta gevinst ved 2–3x risikoen du tok)
- Eksempel: stop 5% under kjøp → ta gevinst ved 10–15% over kjøp
- Partiell realisering: selg 50% ved 1R, la resten løpe med trailing stop

### Diversifisering
- Maks 5% av portefølje per enkelt aksje
- Maks 80% av portefølje investert samtidig (hold 20% i kontanter)
- Spre på tvers av sektorer — unngå at alle posisjoner korrelerer

---

## 6. Mønstergjenkjenning

### Bullish mønstre (kjøpssignal)
- **Hammer**: lang nedre hale, liten kropp øverst → reversal fra nedtrend
- **Bullish engulfing**: stor grønn candle sluker forrige røde → sterkt reversal
- **Morning star**: tre-candle mønster etter nedtrend → bunndannelse
- **Cup & handle**: U-form etterfulgt av liten korreksjon → breakout oppover
- **Higher highs & higher lows**: definisjon på opptrend

### Bearish mønstre (salgssignal)
- **Shooting star**: lang øvre hale øverst i opptrend → reversal
- **Bearish engulfing**: stor rød candle sluker forrige grønne → reversal
- **Head & shoulders**: topp–høyere topp–topp → trend reversal nedover
- **Lower highs & lower lows**: definisjon på nedtrend

---

## 7. Psykologi og atferdsfeller

Disse gjelder like mye for AI som for menneskelige tradere:

- **Confirmation bias**: ikke let etter bevis som støtter din allerede tatte beslutning
- **FOMO (fear of missing out)**: ikke kjøp etter en stor oppgang bare fordi du "gikk glipp av det"
- **Tap-aversjon**: ikke hold tapende posisjoner bare for å unngå å realisere tapet — cut losses raskt
- **Overconfidence**: høy konfidens betyr ikke at du har rett — markedet er alltid siste instans
- **Anchoring**: ikke la kjøpspris bestemme din vurdering av om aksjen er verdt å holde

---

## 8. Oslo Børs — spesifikke hensyn

- **Åpningstid**: 09:00–17:30 CET (07:00–15:30 UTC)
- **Valuta**: Norske kroner (NOK)
- **Sektordominans**: Energi (Equinor), sjømat (Mowi, SalMar), shipping, finans
- **Korrelasjon med oljeprisen**: energiaksjer (EQNR, AKRBP) følger Brent-prisen tett
- **Laksepris**: MOWI, SALM, LSG korrelerer sterkt med spotpris på laks
- **Shipping-syklusen**: HAFNI, BWLPG, MPCC følger fraktratene (Baltic index)
- **Tynn likviditet**: mange small-cap-aksjer på Oslo Børs har lavt volum — store kursutslag på lite handler
- **Sesongeffekter**: jan/feb typisk sterk (nytt år), sommer svakere, høst volatil

---

## 9. Beslutningsrammeverk for signalgenerering

Systemet driver **swing trading** med 1–2 ukers horisont basert på 20 dagers daglig kurshistorikk.

Bruk dette hierarkiet når du vurderer BUY/SELL/HOLD:

```
1. TREND (overordnet retning, 20 dager)
   - Kurs over 20-dagers MA? → bullish
   - Kurs under 20-dagers MA? → bearish
   - Higher highs & higher lows siste uke? → opptrend bekreftet

2. MOMENTUM (daglig)
   - RSI retning og nivå (30/70-grenser)
   - MACD crossover på daglig chart?
   - Relativ styrke mot OSEBX siste 5 dager?

3. VOLUM (bekreftelse)
   - Støtter volumet kursbevegelsen?
   - Volumspike på breakout? → sterk bekreftelse
   - Lavt volum på kursfall → ikke nødvendigvis trend

4. NYHETER (katalysator)
   - Positiv nyhet + teknisk bullish = sterk BUY
   - Negativ nyhet + teknisk bearish = sterk SELL
   - Motstridende signaler → HOLD eller redusér posisjon

5. RISIKO
   - Stop-loss settes ved 7% under kjøpspris (William O'Neil CAN SLIM)
   - Take-profit mål: 14–21% (2R–3R med 7% stop)
   - Passer posisjonsstørrelse med risikoreglene?
   - Er total eksponering innenfor 80%?
```

### Konfidensterskel
- **< 65%**: HOLD — ingen handel
- **65–74%**: svakt signal — liten posisjon
- **75–84%**: moderat signal — normal posisjon
- **≥ 85%**: sterkt signal — full posisjon (maks 5% av portefølje)

---

*Kilder: QuantifiedStrategies, Wealthsimple, LuxAlgo, TradingSim, TradeAtSwing, ACY Markets, MDPI (finansforskning)*

---

<!-- AUTO-LÆRDOMMER START -->
## 10. Lærdommer fra egen handelshistorikk (auto-generert 2026-07-01)

Disse lærdommene er destillert fra systemets egne signaler målt mot faktisk
kursutvikling. Vektlegg dem når du setter konfidens på nye signaler.

- Unngå BUY-signaler på sjømat og shipping helt – disse sektorene har 0 % treffsikkerhet og massive negative avkastninger (gjennomsnitt -11 %, -7 %), noe som tyder på systematiske modellfeil for disse aksjene.

- Øk tilliten til høyeste konfidensnivå (80–100 %) da disse treffer betydelig oftere (69 % vs. 51–53 %), selv om avkastningen per signal er lav – fokuser på kvalitet over kvantitet her.

- SALM.OL er en systematisk feilkilde – fem av fem dårligste signaler er denne aksjen med BUY-anbefalinger som resulteterte i −15 %. Eksluder denne eller omvurder modelleringen for sjømatsektor helt.

- SELL-signaler på fornybar, tech og sjømat treffer perfekt (100 %) – disse sektorene har sterk nedsideprediksjon og bør vektes høyere eller ekspanderes, mens SELL-signaler på finans aldri treffer (0 %) og bør ignoreres.

- Diversifiserte aksjer treffer bedre på BUY (100 %, +13,4 %) enn spesialiserte – vurder om modellen har sterkere prediksjonskraft på bredere, mer likvide papirer.

- Energi og industri er moderat pålitelige for BUY (70 % og 59 %), mens finans er svak (46 %) – fokuser BUY-ressurser på energi og industri, reduser eller omvurder finans-signaler.
<!-- AUTO-LÆRDOMMER END -->
