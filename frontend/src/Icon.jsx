import React from 'react';

const paths = {
  Home: 'M3 11 12 3l9 8M5 10v11h5v-7h4v7h5V10',
  Spending: 'M4 20V4m0 16h17M8 16v-5m5 5V7m5 9V4',
  Coach: 'M3 4h18v13H9l-6 4V4Z',
  Goals: 'M8 3h8v7a4 4 0 0 1-8 0V3Zm0 1H4v3a4 4 0 0 0 4 4m8-7h4v3a4 4 0 0 1-4 4m-4 3v5m-5 2h10v-2H7v2Z',
};

export default function Icon({ name }) {
  return <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor"
    strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={paths[name]} />
  </svg>;
}
