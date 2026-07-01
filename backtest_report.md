# Backtest-rapport (2026-07-01)

Auto-generert hver søndag av GitHub Actions. Replayer alle lagrede
AI-signaler (663 stk over 6 børsdager) mot faktisk kurshistorikk.

## Parametergrid

```
 Stop  Trail  Konf |   Sluttverdi  Avkastn.  Salg  Vinn  Åpne
-----------------------------------------------------------------
   5%     ja   70% |       98,004    -2.00%     6     1     8
   5%     ja   75% |       95,032    -4.97%    11     0     7
   5%     ja   80% |      100,000    +0.00%     0     0     0
   5%    nei   70% |       98,125    -1.87%     4     0     8
   5%    nei   75% |       97,520    -2.48%     5     0     7
   5%    nei   80% |      100,000    +0.00%     0     0     0
   7%     ja   70% |       99,400    -0.60%     4     1     8 ← dagens
   7%     ja   75% |       97,710    -2.29%     4     0     7
   7%     ja   80% |      100,000    +0.00%     0     0     0
   7%    nei   70% |       97,924    -2.08%     4     0     8
   7%    nei   75% |       98,005    -2.00%     3     0     7
   7%    nei   80% |      100,000    +0.00%     0     0     0
  10%     ja   70% |       96,549    -3.45%     5     0     8
  10%     ja   75% |       97,051    -2.95%     4     0     7
  10%     ja   80% |      100,000    +0.00%     0     0     0
  10%    nei   70% |       97,561    -2.44%     4     0     8
  10%    nei   75% |       97,430    -2.57%     3     0     7
  10%    nei   80% |      100,000    +0.00%     0     0     0
```

## Beste kombinasjon

Stop-loss 5%, trailing ja, konfidensterskel 80%
→ 100,000 NOK (+0.00%)

Dagens produksjonsparametre: stop-loss 7%, trailing ja, konfidens 70%.

*NB: kort historikk gir indikative resultater. Ikke endre parametre basert
på én ukes data — se etter mønstre som holder seg over flere uker.*
