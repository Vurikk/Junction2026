// The API supplies periods chronologically. Limit display only; keep financial values unchanged.
export const chartPeriods = history => history?.period === 'week' ? history.periods?.slice(-8) : history?.periods;
