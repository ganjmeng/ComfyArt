/** Bind a paid quote answer to its originating chat; a missing/invalid ack is uncertain. */
export function createQuoteAnswer(
  chatId: string | null,
  askId: string,
  request: (path: string, body: { selected: string[]; other_text: string }) => Promise<unknown>,
) {
  return async (selected: string[]): Promise<void> => {
    if (!chatId || !askId) throw new Error('Missing quote conversation')
    const ack = await request(`/comfyart/bot/chats/${encodeURIComponent(chatId)}/asks/${encodeURIComponent(askId)}/answer`, {
      selected, other_text: '',
    })
    if (!ack || typeof ack !== 'object' || !('ok' in ack) || ack.ok !== true) {
      throw new Error('Quote acknowledgement missing')
    }
  }
}
