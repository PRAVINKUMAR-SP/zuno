export default function ZunoLogo({ size = 28, className = '' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Zuno logo"
    >
      <rect
        x="1.5"
        y="1.5"
        width="29"
        height="29"
        rx="8.5"
        fill="#16181f"
        stroke="rgba(255,255,255,0.16)"
        strokeWidth="1.25"
      />
      <path
        d="M10.5 11H21.5L10.5 21H21.5"
        stroke="#F4F4F5"
        strokeWidth="2.1"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="21.5" cy="11" r="1.6" fill="#34D399" />
    </svg>
  );
}

