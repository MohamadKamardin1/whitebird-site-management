/** White Bird role-aware navigation: UI visibility follows the capability matrix; API authorization remains authoritative. */
import { Archive, Bell, Building2, CalendarDays, ClipboardCheck, ClipboardList, FileBarChart2, Gauge, HardHat, LayoutDashboard, PackageCheck, PackageSearch, Settings2, UsersRound, UserRoundPlus, UserCog, GraduationCap } from "lucide-react";

export type NavEntry = { href: string; label: string; icon: typeof LayoutDashboard; roles?: string[] };

export const primaryNavigation: NavEntry[] = [
  { href: "/", label: "Today", icon: LayoutDashboard },
  { href: "/admin", label: "Administration", icon: Settings2, roles: ["system_admin"] },
  { href: "/admin/users", label: "Users & roles", icon: UserCog, roles: ["system_admin"] },
  { href: "/admin/estate", label: "Sites, zones & GIS", icon: Building2, roles: ["system_admin"] },
  { href: "/admin/supervisor-timetables", label: "Supervisor timetables", icon: CalendarDays, roles: ["system_admin"] },
  { href: "/admin/integrations", label: "Integration settings", icon: Settings2, roles: ["system_admin"] },
  { href: "/sites", label: "Sites & zones", icon: Building2, roles: ["general_supervisor", "assistant_general_supervisor", "zone_supervisor", "management_viewer"] },
  { href: "/hr/onboarding", label: "HR onboarding", icon: UserRoundPlus, roles: ["hr"] },
  { href: "/hr/people", label: "People registry", icon: UsersRound, roles: ["hr", "system_admin", "general_supervisor"] },
  { href: "/hr/assignments", label: "Assignments & shifts", icon: ClipboardList, roles: ["hr", "system_admin"] },
  { href: "/trainees", label: "Trainee management", icon: GraduationCap, roles: ["hr", "site_supervisor", "system_admin", "general_supervisor", "assistant_general_supervisor", "zone_supervisor"] },
  { href: "/attendance", label: "Attendance", icon: ClipboardCheck, roles: ["system_admin", "general_supervisor", "assistant_general_supervisor", "zone_supervisor", "site_supervisor"] },
  { href: "/cleanliness", label: "Daily cleanliness", icon: ClipboardCheck, roles: ["system_admin", "general_supervisor", "assistant_general_supervisor", "zone_supervisor", "site_supervisor"] },
  { href: "/supervision/roster", label: "My supervision timetable", icon: ClipboardList, roles: ["assistant_general_supervisor", "zone_supervisor"] },
  { href: "/operations/issues", label: "Issues & jobs", icon: HardHat, roles: ["system_admin", "general_supervisor", "assistant_general_supervisor", "zone_supervisor", "site_supervisor"] },
  { href: "/store-control", label: "Store control", icon: PackageCheck, roles: ["store_manager", "system_admin", "general_supervisor"] },
  { href: "/stores", label: "Stores & stock", icon: PackageSearch, roles: ["store_manager", "system_admin", "general_supervisor", "assistant_general_supervisor", "zone_supervisor", "site_supervisor"] },
  { href: "/reports", label: "Reports", icon: FileBarChart2, roles: ["system_admin", "general_supervisor", "assistant_general_supervisor", "zone_supervisor", "site_supervisor", "store_manager", "hr"] },
];

export const secondaryNavigation: NavEntry[] = [
  { href: "/notifications", label: "Notifications", icon: Bell },
  { href: "/settings/profile", label: "Account & security", icon: Gauge },
  { href: "/reports", label: "Report archive", icon: Archive },
];

export const roleLabels: Record<string, string> = {
  system_admin: "System administrator",
  hr: "Human resources",
  store_manager: "Store manager",
  general_supervisor: "General supervisor",
  assistant_general_supervisor: "Assistant general supervisor",
  zone_supervisor: "Zone supervisor",
  site_supervisor: "Site manager / supervisor",
  management_viewer: "Management viewer",
};

export function canSee(role: string | undefined, roles: string[] = []) { return roles.length === 0 || Boolean(role && roles.includes(role)); }
