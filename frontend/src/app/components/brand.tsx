import Link from "next/link";

/** Two linked image frames form a compact Q-shaped exchange mark. */
export default function Brand() {
  return (
    <Link className="brand" href="/" aria-label="QPQData home">
      <svg
        className="brand-mark"
        viewBox="0 0 48 48"
        fill="none"
        aria-hidden="true"
      >
        <rect x="3" y="17" width="28" height="28" rx="9" fill="#142440" />
        <rect x="17" y="3" width="28" height="28" rx="9" fill="#2e63d9" />
        <rect
          x="24"
          y="10"
          width="14"
          height="14"
          rx="4"
          stroke="white"
          strokeWidth="2.5"
        />
        <path
          d="m33 20 6 6"
          stroke="white"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        <path
          d="M17 24h-3a4 4 0 0 0-4 4v6a4 4 0 0 0 4 4h6a4 4 0 0 0 4-4v-3"
          stroke="white"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        <path
          d="m19 33 6 6"
          stroke="white"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        <circle cx="10" cy="10" r="3" fill="#2b9676" />
      </svg>
      <span className="brand-wordmark">
        QPQ<span className="brand-accent">Data</span>
      </span>
    </Link>
  );
}
