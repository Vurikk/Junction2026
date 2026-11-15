import React from 'react';

export default function PlanTargetLabel({ viewBox }) {
  if (!viewBox) return null;
  return <g transform={`translate(${viewBox.x - 23}, ${viewBox.y - 10})`} aria-hidden="true">
    <svg width="18" height="20" viewBox="0 0 24 24" fill="none" stroke="#999999"
      strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 3h8v7a4 4 0 0 1-8 0V3Zm0 1H4v3a4 4 0 0 0 4 4m8-7h4v3a4 4 0 0 1-4 4m-4 3v5m-5 2h10v-2H7v2Z" />
    </svg>
  </g>;
}
