export function categoriesFor(period) {
  return Object.keys(period?.categories || {}).filter(name =>
    name.trim() && !['unknown', 'uncategorized'].includes(name.trim().toLowerCase()));
}

export function eligibleMonths(history, today = new Date().toISOString().slice(0, 10)) {
  return (history?.periods || []).filter(period =>
    !period.partial && period.end < today && categoriesFor(period).length > 0).slice().reverse();
}

export function preferredCategory(period) {
  const names = categoriesFor(period);
  return names.find(name => name.trim().toLowerCase() === 'restaurants') || names[0] || '';
}

export function validReduction(value) {
  return /^\d+(\.\d{1,2})?$/.test(value) && Number(value) >= 0 && Number(value) <= 100;
}
