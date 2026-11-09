/**
 * FinSight AI — Currency, Date, and Metric Formatters
 * Formats financial figures with standard Indian locale (en-IN) conventions.
 */

export function formatINR(amount: number): string {
  const isNegative = amount < 0;
  const absAmount = Math.abs(amount);
  const formatted = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(absAmount);

  return isNegative ? `-${formatted}` : formatted;
}

export function formatCompactINR(amount: number): string {
  const isNegative = amount < 0;
  const abs = Math.abs(amount);

  let formatted = '';
  if (abs >= 10000000) {
    // Crores
    formatted = `₹${(abs / 10000000).toFixed(2)} Cr`;
  } else if (abs >= 100000) {
    // Lakhs
    formatted = `₹${(abs / 100000).toFixed(2)} L`;
  } else if (abs >= 1000) {
    // Thousands
    formatted = `₹${(abs / 1000).toFixed(1)}k`;
  } else {
    formatted = `₹${abs.toFixed(0)}`;
  }

  return isNegative ? `-${formatted}` : formatted;
}

export function formatDate(dateString: string): string {
  if (!dateString) return '—';
  // dateString is typically 'YYYY-MM-DD'
  const parts = dateString.split('-');
  if (parts.length === 3) {
    const year = parseInt(parts[0], 10);
    const month = parseInt(parts[1], 10) - 1;
    const day = parseInt(parts[2], 10);
    const date = new Date(year, month, day);
    return date.toLocaleDateString('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  }
  return dateString;
}

export function formatMonthName(monthString: string): string {
  if (!monthString) return '—';
  // monthString is 'YYYY-MM'
  const parts = monthString.split('-');
  if (parts.length === 2) {
    const year = parseInt(parts[0], 10);
    const month = parseInt(parts[1], 10) - 1;
    const date = new Date(year, month, 1);
    return date.toLocaleDateString('en-IN', {
      month: 'short',
      year: 'numeric',
    });
  }
  return monthString;
}
