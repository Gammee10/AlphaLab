// Inline SVG icon set (stroke-based, Lucide-style geometry). Rendering only.

import type { ReactNode } from "react";

function Wrap({ size, children }: { size: number; children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {children}
    </svg>
  );
}

export type IconProps = { size?: number };

export const IcPulse = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <path d="M3 12h4l2-7 4 14 2-7h6" />
  </Wrap>
);

export const IcLayers = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <path d="M12 3 2 8.4 12 13.8l10-5.4L12 3z" />
    <path d="m2 14 10 5.4L22 14" />
  </Wrap>
);

export const IcPlay = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <path d="m6 4.5 13 7.5-13 7.5v-15z" />
  </Wrap>
);

export const IcSwap = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <path d="M17 3.5 21 7.5l-4 4" />
    <path d="M21 7.5H8" />
    <path d="M7 20.5 3 16.5l4-4" />
    <path d="M3 16.5h13" />
  </Wrap>
);

export const IcSpark = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <path d="M12 2.5 13.8 9l6.5 1.8-6.5 1.8L12 19l-1.8-6.4-6.5-1.8L10.2 9 12 2.5z" />
  </Wrap>
);

export const IcCoin = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5v9M14.8 9.4c0-1-1.3-1.7-2.8-1.7s-2.8.7-2.8 1.7 1 1.5 2.8 1.9 2.8 1 2.8 1.9-1.3 1.7-2.8 1.7-2.8-.7-2.8-1.7" />
  </Wrap>
);

export const IcDb = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <ellipse cx="12" cy="5.5" rx="7.5" ry="2.8" />
    <path d="M4.5 5.5v13c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8v-13" />
    <path d="M4.5 12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8" />
  </Wrap>
);

export const IcWarn = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <path d="M12 9v4.5m0 3h.01" />
    <path d="M10.3 3.9 2.4 17.5A2 2 0 0 0 4.1 20.5h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
  </Wrap>
);

export const IcInfo = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 16v-4.5m0-3.5h.01" />
  </Wrap>
);

export const IcCheck = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <path d="m4.5 12.5 5 5 10-11" />
  </Wrap>
);

export const IcX = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <path d="m6 6 12 12M18 6 6 18" />
  </Wrap>
);

export const IcSearch = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20.5 20.5-4.4-4.4" />
  </Wrap>
);

export const IcSun = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2.5v2m0 15v2m-9.5-9.5h2m15 0h2M5 5l1.4 1.4M17.6 17.6 19 19M19 5l-1.4 1.4M6.4 17.6 5 19" />
  </Wrap>
);

export const IcMoon = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <path d="M20.5 14.5A8.5 8.5 0 1 1 9.5 3.5a7 7 0 0 0 11 11z" />
  </Wrap>
);

export const IcPanel = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <rect x="3" y="4" width="18" height="16" rx="2.5" />
    <path d="M9.5 4v16" />
  </Wrap>
);

export const IcInbox = ({ size = 24 }: IconProps) => (
  <Wrap size={size}>
    <path d="M21.5 12.5h-5l-1.7 2.6h-5.6l-1.7-2.6H2.5" />
    <path d="M5 5.6 2.5 10.5v6a2 2 0 0 0 2 2h15a2 2 0 0 0 2-2v-6L19 5.6a2 2 0 0 0-1.8-1.1H6.8A2 2 0 0 0 5 5.6z" />
  </Wrap>
);

export const IcPlus = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <path d="M12 5.5v13m-6.5-6.5h13" />
  </Wrap>
);

export const IcChevron = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <path d="m9 5.5 6.5 6.5L9 18.5" />
  </Wrap>
);

export const IcBack = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <path d="M19 12H5m0 0 6-6m-6 6 6 6" />
  </Wrap>
);

export const IcSend = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <path d="m21.5 2.5-10 10" />
    <path d="M21.5 2.5 15 21l-3.5-8.5L3 9l18.5-6.5z" />
  </Wrap>
);

export const IcClock = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7v5.2l3.2 1.9" />
  </Wrap>
);

export const IcList = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <path d="M8.5 6.5h12m-12 5.5h12m-12 5.5h12" />
    <path d="M4 6h.01M4 12h.01M4 18h.01" />
  </Wrap>
);

export const IcCode = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <path d="m8 8-4 4 4 4m8-8 4 4-4 4" />
  </Wrap>
);

export const IcChart = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <path d="M3 19.5V5m0 14.5h18" />
    <path d="m6 15 3.5-4 3 2.5L18 7" />
    <circle cx="18" cy="7" r="1.4" />
  </Wrap>
);

export const IcShield = ({ size = 16 }: IconProps) => (
  <Wrap size={size}>
    <path d="M12 2.8 5 5.3v6.2c0 4.4 3 7.6 7 9.7 4-2.1 7-5.3 7-9.7V5.3L12 2.8z" />
  </Wrap>
);
