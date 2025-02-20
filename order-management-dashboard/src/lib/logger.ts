type Level = 'info' | 'warn' | 'error'

function log(level: Level, event: string, data?: Record<string, unknown>): void {
  const entry = {
    ts: new Date().toISOString(),
    level,
    event,
    ...data,
  }
  if (level === 'error') {
    console.error(JSON.stringify(entry))
  } else {
    console.log(JSON.stringify(entry))
  }
}

export const logger = {
  info:  (event: string, data?: Record<string, unknown>) => log('info',  event, data),
  warn:  (event: string, data?: Record<string, unknown>) => log('warn',  event, data),
  error: (event: string, data?: Record<string, unknown>) => log('error', event, data),
}
