import { thresholdCredits } from '../../src/usd'
console.log(JSON.stringify([50, 0, 1, 2.25, 10, 0.125, NaN].map(thresholdCredits)))
