# OptStrat

Python-based app to find options contracts that adhere to a configured strategy using Poylgon.io data.

## SUPPORTED STRATEGIES

### PRE-EARNINGS LONG STRADDLE

* On a high-level this means to buy both call/put options 7-30 days before earnings and to sell the day or the hours leading to the earnings to capitalize on the IV expansion and avoid IV crush.
* * Low theta to avoid time decay. 
* * High vega to maximize IV swings.

* Give input strategy as 'longStraddleIV' to use.

## NEXT STEPS

* The app is abstracted such that any different strategy can be easily added. Will explore adding more strategies in the future.
