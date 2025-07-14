import React from "react";

export default function EmptyState() {
  return (
    <div className="text-center text-gray-400 mt-8">
      <svg className="mx-auto h-12 w-12 text-gray-300" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 17v-2a4 4 0 018 0v2m-4-4V7m0 0a4 4 0 00-8 0v2a4 4 0 008 0V7z" />
      </svg>
      <p className="mt-2">No data to display. Upload and process a CSV to see results.</p>
    </div>
  );
} 