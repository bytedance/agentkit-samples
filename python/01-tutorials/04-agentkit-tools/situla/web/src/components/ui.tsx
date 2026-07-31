import type { ReactNode, SVGProps } from "react";

function Icon({ children, ...props }: SVGProps<SVGSVGElement> & { children: ReactNode }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{children}</svg>;
}

export function Logo({ large = false, compact = false }: { large?: boolean; compact?: boolean }) {
  return <div className={`logo ${large ? "large" : ""} ${compact ? "compact" : ""}`}><svg viewBox="0 0 32 32" aria-hidden="true"><ellipse className="logo-orbit logo-orbit-wide" cx="16" cy="16" rx="13.2" ry="6.1" /><ellipse className="logo-orbit logo-orbit-tall" cx="16" cy="16" rx="5.8" ry="13" transform="rotate(-34 16 16)" /><circle className="logo-planet logo-planet-a" cx="7.2" cy="8" r="2.45" /><circle className="logo-planet logo-planet-b" cx="24.7" cy="23.6" r="2.05" /><circle className="logo-dot" cx="25.1" cy="7.4" r=".85" /><path className="logo-star" d="M16 2.7 18.3 11l5.9-4.2-3.3 6.6 8.4 2.6-8.4 2.6 3.3 6.6-5.9-4.2-2.3 8.3-2.3-8.3-5.9 4.2 3.3-6.6L2.7 16l8.4-2.6-3.3-6.6 5.9 4.2L16 2.7Z" /><path className="logo-star-core" d="M16 10.2c.6 3.4 2.4 5.2 5.8 5.8-3.4.6-5.2 2.4-5.8 5.8-.6-3.4-2.4-5.2-5.8-5.8 3.4-.6 5.2-2.4 5.8-5.8Z" /></svg></div>;
}

export const MenuIcon = () => <Icon><path d="M4 7h16M4 12h16M4 17h16" /></Icon>;
export const CloseIcon = () => <Icon><path d="m6 6 12 12M18 6 6 18" /></Icon>;
export const ArrowLeftIcon = () => <Icon><path d="m10 6-6 6 6 6M4 12h16" /></Icon>;
export const PlusIcon = () => <Icon><path d="M12 5v14M5 12h14" /></Icon>;
export const CubeIcon = () => <Icon><path d="m12 2 8 4.5v9L12 22l-8-4.5v-9Z" /><path d="m4 6.5 8 4.5 8-4.5M12 11v11" /></Icon>;
export const CheckIcon = () => <Icon><path d="m5 12 4 4L19 6" /></Icon>;
export const PaperclipIcon = () => <Icon><path d="m20.5 11.5-8.2 8.2a6 6 0 0 1-8.5-8.5l9-9a4 4 0 0 1 5.7 5.7l-9 9a2 2 0 1 1-2.8-2.8l8.2-8.2" /></Icon>;
export const ModelIcon = () => <Icon><path d="M12 3 4 7v10l8 4 8-4V7Z" /><path d="m8 9 4 2 4-2M12 11v5" /></Icon>;
export const SkillIcon = () => <Icon><path d="M12 3c.7 4.8 3.2 7.3 8 8-4.8.7-7.3 3.2-8 8-.7-4.8-3.2-7.3-8-8 4.8-.7 7.3-3.2 8-8Z" /><path d="M19 2v4M21 4h-4" /></Icon>;
export const ChatIcon = () => <Icon><path d="M20 15a4 4 0 0 1-4 4H8l-4 2V7a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4Z" /></Icon>;
export const ArchiveIcon = () => <Icon><path d="M4 7h16M6 7v13h12V7M9 11h6M5 3h14l1 4H4Z" /></Icon>;
export const MoreVerticalIcon = () => <Icon><circle cx="12" cy="5" r="1" fill="currentColor" stroke="none" /><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" /><circle cx="12" cy="19" r="1" fill="currentColor" stroke="none" /></Icon>;
export const SunIcon = () => <Icon><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.66 6.34l1.41-1.41" /></Icon>;
export const MoonIcon = () => <Icon><path d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5 8.5 8.5 0 1 0 20.5 14.2Z" /></Icon>;
export const PulseIcon = () => <Icon><path d="M3 12h4l2-7 4 14 2-7h6" /></Icon>;
export const RefreshIcon = () => <Icon><path d="M21 12a9 9 0 0 0-15.2-6.5L3 8" /><path d="M3 3v5h5M3 12a9 9 0 0 0 15.2 6.5L21 16M16 16h5v5" /></Icon>;
export const TerminalIcon = () => <Icon><path d="m5 7 4 4-4 4M11 17h8" /></Icon>;
export const BrowserIcon = () => <Icon><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M3 9h18M7 6.5h.01M10 6.5h.01" /></Icon>;
export const DisconnectIcon = () => <Icon><path d="M10 7V5a2 2 0 0 1 2-2h7a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-7a2 2 0 0 1-2-2v-2M3 12h12M7 8l-4 4 4 4" /></Icon>;
export const LogoutIcon = () => <Icon><path d="M10 5V4a2 2 0 0 1 2-2h7a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2h-7a2 2 0 0 1-2-2v-1M14 12H3M7 8l-4 4 4 4" /></Icon>;
export const LinkIcon = () => <Icon><path d="M10 13a5 5 0 0 0 7.5.5l2-2a5 5 0 0 0-7-7l-1.15 1.15M14 11a5 5 0 0 0-7.5-.5l-2 2a5 5 0 0 0 7 7l1.15-1.15" /></Icon>;
export const UserIcon = () => <Icon><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></Icon>;
export const ArrowUpIcon = () => <Icon><path d="m12 19 0-14M6 11l6-6 6 6" /></Icon>;
export const ArrowDownIcon = () => <Icon><path d="m12 5 0 14M18 13l-6 6-6-6" /></Icon>;
export const AlertIcon = () => <Icon><path d="M10.3 3.7 2.4 18a2 2 0 0 0 1.8 3h15.6a2 2 0 0 0 1.8-3L13.7 3.7a2 2 0 0 0-3.4 0ZM12 9v4M12 17h.01" /></Icon>;
export const LockIcon = () => <Icon><rect x="4" y="10" width="16" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></Icon>;
export const EyeIcon = () => <Icon><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /></Icon>;
export const EyeOffIcon = () => <Icon><path d="m3 3 18 18M10.6 10.6a2 2 0 0 0 2.8 2.8M9.9 4.2A10.7 10.7 0 0 1 12 4c6.5 0 10 8 10 8a18.4 18.4 0 0 1-2 3M6.6 6.6C3.5 8.6 2 12 2 12s3.5 8 10 8a9.9 9.9 0 0 0 4.2-.9" /></Icon>;
export const ShieldIcon = () => <Icon><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" /><path d="m9 12 2 2 4-4" /></Icon>;
export const SearchIcon = () => <Icon><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></Icon>;
export const FolderIcon = () => <Icon><path d="M3 6.5A2.5 2.5 0 0 1 5.5 4H9l2 2h7.5A2.5 2.5 0 0 1 21 8.5v8A2.5 2.5 0 0 1 18.5 19h-13A2.5 2.5 0 0 1 3 16.5Z" /></Icon>;
export function ChevronIcon({ open }: { open: boolean }) { return <Icon className={open ? "rotated" : ""}><path d="m9 18 6-6-6-6" /></Icon>; }
export function Spinner() { return <span className="spinner" />; }
