// #227: cost-confirm cancel is its own tool-row state
import { stepState } from '../../src/ui/stepState'
console.log(JSON.stringify([
  stepState(undefined),
  stepState({ status: 'done', text: '{"id":"a","status":"done"}' }),
  stepState({ status: 'error', text: 'boom' }),
  stepState({ status: 'done', text: '[{"id":"a","status":"declined","cancelled":true}]' }),
  stepState({ status: 'error', text: 'Cancelled this generation; nothing was charged.' }),
  stepState({ status: 'done', text: '已取消该生成，未扣费。' }),
]))
