/**
 * Helper to format date strings from YYYY-MM-DD to DD-MM-YYYY
 */
export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr || dateStr === 'None' || dateStr === 'Checking...' || dateStr === 'Offline') {
    return dateStr || '';
  }
  
  // Format matches YYYY-MM-DD
  const parts = dateStr.split('-');
  if (parts.length === 3) {
    if (parts[0].length === 4) {
      return `${parts[2]}-${parts[1]}-${parts[0]}`;
    }
  }
  
  return dateStr;
}
