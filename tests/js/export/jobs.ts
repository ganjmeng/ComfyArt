export const errorText = (e: unknown) => String((e as Error)?.message ?? e)
