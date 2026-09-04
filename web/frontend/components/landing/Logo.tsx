// Abstract two-stroke mark suggesting a held wing angle. No bird, no fill.
export function Logo({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="#26D9E4"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M2 15 L11 8" />
      <path d="M11 8 L22 4 L13 13" />
    </svg>
  );
}
