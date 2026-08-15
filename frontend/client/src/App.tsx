/** Coastal Ledger route composition: protected, permission-aware operations workspaces with no navigation dead ends. */
import { ReactNode } from "react";
import { Route, Switch } from "wouter";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import ErrorBoundary from "@/components/ErrorBoundary";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import LoginPage from "@/pages/LoginPage";
import DashboardPage from "@/pages/DashboardPage";
import ResourceWorkspace from "@/pages/ResourceWorkspace";
import AttendancePage from "@/pages/AttendancePage";
import NotificationsPage from "@/pages/NotificationsPage";
import ProfilePage from "@/pages/ProfilePage";
import NotFound from "@/pages/NotFound";
import MarketingPage from "@/pages/MarketingPage";

function Protected({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  if (status === "checking") return <div className="flex min-h-screen items-center justify-center bg-[#F8F5EC]"><span className="h-9 w-9 animate-spin rounded-full border-[3px] border-[#C7DED9] border-t-[#0F7667]" /></div>;
  return status === "authenticated" ? <>{children}</> : <LoginPage />;
}
function ProtectedPage({ children }: { children: ReactNode }) { return <Protected>{children}</Protected>; }

function Router() {
  return <Switch>
    <Route path="/marketing" component={MarketingPage} />
    <Route path="/login" component={LoginPage} />
    <Route path="/"><ProtectedPage><DashboardPage /></ProtectedPage></Route>
    <Route path="/sites"><ProtectedPage><ResourceWorkspace config={{ eyebrow: "Organisation hierarchy", title: "Sites and zones, in one clear portfolio.", description: "Navigate the operating estate through permitted zones, sites, supervisors, configuration, and live site context.", endpoint: "/sites", filterLabel: "sites and zones", emptyTitle: "No visible sites", emptyDescription: "Your current role has not returned visible site records. Check your assigned scope or contact a system administrator." }} /></ProtectedPage></Route>
    <Route path="/people/cleaners"><ProtectedPage><ResourceWorkspace config={{ eyebrow: "People operations", title: "A cleaner registry built for responsible review.", description: "Search and review authorised cleaner records, document states, and onboarding readiness without exposing sensitive data outside policy.", endpoint: "/cleaners", action: "cleaner", actionPermission: "accounts.manage_cleaners", filterLabel: "cleaners" }} /></ProtectedPage></Route>
    <Route path="/people/assignments"><ProtectedPage><ResourceWorkspace config={{ eyebrow: "Work allocation", title: "Assignments that match the day’s reality.", description: "Find cleaner-site assignments and schedules, then use the backend-controlled lifecycle actions for active, suspended, and ended work.", endpoint: "/assignments", filterLabel: "assignments" }} /></ProtectedPage></Route>
    <Route path="/attendance"><ProtectedPage><AttendancePage /></ProtectedPage></Route>
    <Route path="/inspections"><ProtectedPage><ResourceWorkspace config={{ eyebrow: "Quality assurance", title: "Inspection evidence, ready for review.", description: "Start from current inspection work, templates, results, and the evidence-led workflow required to move an inspection through review.", endpoint: "/inspections", action: "inspection", filterLabel: "inspections" }} /></ProtectedPage></Route>
    <Route path="/operations/issues"><ProtectedPage><ResourceWorkspace config={{ eyebrow: "Operations queue", title: "Issues and jobs that keep ownership visible.", description: "Search current operational risk, raise a well-defined issue, and move authorised jobs through assignment, evidence, verification, and closure.", endpoint: "/issues", action: "issue", filterLabel: "issues and jobs" }} /></ProtectedPage></Route>
    <Route path="/stores"><ProtectedPage><ResourceWorkspace config={{ eyebrow: "Stores & stock", title: "Supply signals before they become delays.", description: "Monitor your authorised stores, stock items, movements, requests, and low-stock conditions from an audit-ready workspace.", endpoint: "/stores", action: "stock_request", filterLabel: "stores and stock" }} /></ProtectedPage></Route>
    <Route path="/reports"><ProtectedPage><ResourceWorkspace config={{ eyebrow: "Management reporting", title: "A reporting chain with clear handovers.", description: "View daily site reports in their structured workflow and use the reporting status workspace to identify the next accountable review or submission.", endpoint: "/reports/site", action: "general_report", filterLabel: "site reports" }} /></ProtectedPage></Route>
    <Route path="/notifications"><ProtectedPage><NotificationsPage /></ProtectedPage></Route>
    <Route path="/settings/profile"><ProtectedPage><ProfilePage /></ProtectedPage></Route>
    <Route component={NotFound} />
  </Switch>;
}

export default function App() { return <ErrorBoundary><ThemeProvider defaultTheme="light"><TooltipProvider><AuthProvider><Router /><Toaster richColors position="top-right" /></AuthProvider></TooltipProvider></ThemeProvider></ErrorBoundary>; }
