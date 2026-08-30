"use client";

import Image from "next/image";

async function createItem() {
  const response = await fetch(`http://localhost:8000/re/${5}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    
  });

  if (!response.ok) {
    throw new Error(`Error: ${response.status}`);
  }

  const data = await response.json();
  console.log(data);
}

export default function Home() {
  return (
    <div>
      <button onClick={createItem}>
        Create Item
      </button>
    </div>
  );
}