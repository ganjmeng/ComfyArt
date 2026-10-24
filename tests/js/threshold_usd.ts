import { thresholdUsd } from '../../src/usd'
console.log(JSON.stringify([0.5, 0, 1, 2.25, 10, 0.125, NaN].map(thresholdUsd)))
