import React from "react";

export default function Button({ children, variant = "primary", ...props }) {
  const base = "px-4 py-2 rounded font-semibold focus:outline-none transition ";
  const variants = {
    primary: base + "bg-blue-600 text-white hover:bg-blue-700",
    secondary: base + "bg-gray-200 text-gray-800 hover:bg-gray-300",
    success: base + "bg-green-600 text-white hover:bg-green-700",
  };
  return (
    <button className={variants[variant]} {...props}>
      {children}
    </button>
  );
} 