/** Coastal Ledger route composition: protected, permission-aware operations workspaces with no navigation dead ends. */
import { ReactNode } from "react";
import { Route, Router as WouterRouter, Switch } from "wouter";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import ErrorBoundary from "@/components/ErrorBoundary";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import LoginPage from "@/pages/LoginPage";
import DashboardPage from "@/pages/DashboardPage";
import ResourceWorkspace from "@/pages/ResourceWorkspace";
import AttendancePage from "@/pages/AttendancePage";
import CleanlinessPage from "@/pages/CleanlinessPage";
import NotificationsPage from "@/pages/NotificationsPage";
import ProfilePage from "@/pages/ProfilePage";
import NotFound from "@/pages/NotFound";
import MarketingPage from "@/pages/MarketingPage";
import { ReportsPage, SiteIssuesPage, StockRequestsPage } from "@/pages/OperationalWorkflowsPage";
import RoleWorkspacesPage from "@/pages/RoleWorkspacesPage";
import AdminEstatePage from "@/pages/AdminEstatePage";
import StoreControlPage from "@/pages/StoreControlPage";
import IntegrationSettingsPage from "@/pages/IntegrationSettingsPage";
import TraineeManagementPage from "@/pages/TraineeManagementPage";
import RemunerationPage from "@/pages/RemunerationPage";
import AdminRemunerationPage from "@/pages/AdminRemunerationPage";
import AdminUsersPage from "@/pages/AdminUsersPage";
import InboxPage from "@/pages/InboxPage";
import { SupervisorRosterPage, SupervisorTimetableAdminPage } from "@/pages/SupervisorRosterPage";
import { AdminTimetableWizardPage, PersonalSupervisorSchedulerPage } from "@/pages/TimetablePages";

function Protected({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  if (status === "checking") return <div className="flex min-h-screen items-center justify-center bg-[#F8F5EC]"><span className="h-9 w-9 animate-spin rounded-full border-[3px] border-[#C7DED9] border-t-[#0F7667]" /></div>;
  return status === "authenticated" ? <>{children}</> : <LoginPage />;
}
function ProtectedPage({ children }: { children: ReactNode }) { return <Protected>{children}</Protected>; }

function Router() {
  const routeBase = typeof window !== "undefined" && window.location.pathname.startsWith("/app") ? "/app" : "";
  return <WouterRouter base={routeBase}><Switch>
    <Route path="/marketing" component={MarketingPage} />
    <Route path="/login" component={LoginPage} />
    <Route path="/"><ProtectedPage><DashboardPage /></ProtectedPage></Route>
    <Route path="/admin"><ProtectedPage><RoleWorkspacesPage mode="admin" /></ProtectedPage></Route>
    <Route path="/admin/estate"><ProtectedPage><AdminEstatePage /></ProtectedPage></Route>
    <Route path="/admin/integrations"><ProtectedPage><IntegrationSettingsPage /></ProtectedPage></Route>
    <Route path="/admin/remuneration"><ProtectedPage><AdminRemunerationPage /></ProtectedPage></Route>
    <Route path="/admin/users"><ProtectedPage><AdminUsersPage /></ProtectedPage></Route>
    <Route path="/admin/supervisor-timetables"><ProtectedPage><AdminTimetableWizardPage /></ProtectedPage></Route>
    <Route path="/sites"><ProtectedPage><ResourceWorkspace config={{ eyebrow: "Organisation hierarchy", title: "Sites and zones, in one clear portfolio.", description: "Navigate the operating estate through permitted zones, sites, supervisors, configuration, and live site context.", endpoint: "/sites", filterLabel: "sites and zones", emptyTitle: "No visible sites", emptyDescription: "Your current role has not returned visible site records. Check your assigned scope or contact a system administrator." }} /></ProtectedPage></Route>
    <Route path="/hr/onboarding"><ProtectedPage><RoleWorkspacesPage mode="hr" /></ProtectedPage></Route>
    <Route path="/hr/people"><ProtectedPage><ResourceWorkspace config={{ eyebrow: "HR people registry", title: "Cleaner records, documents, and onboarding readiness.", description: "Review workforce records through the HR-controlled lifecycle.", endpoint: "/cleaners", action: "cleaner", actionPermission: "accounts.manage_cleaners", filterLabel: "cleaners" }} /></ProtectedPage></Route>
    <Route path="/hr/assignments"><ProtectedPage><ResourceWorkspace config={{ eyebrow: "HR workforce planning", title: "Assignments and shifts with effective dates.", description: "Maintain the official cleaner-to-site and cleaner-to-shift handover.", endpoint: "/assignments", filterLabel: "assignments" }} /></ProtectedPage></Route>
    <Route path="/store-control"><ProtectedPage><StoreControlPage /></ProtectedPage></Route>
    <Route path="/trainees"><ProtectedPage><TraineeManagementPage /></ProtectedPage></Route>
    <Route path="/people/cleaners"><ProtectedPage><ResourceWorkspace config={{ eyebrow: "People operations", title: "A cleaner registry built for responsible review.", description: "Search and review authorised cleaner records, document states, and onboarding readiness without exposing sensitive data outside policy.", endpoint: "/cleaners", action: "cleaner", actionPermission: "accounts.manage_cleaners", filterLabel: "cleaners" }} /></ProtectedPage></Route>
    <Route path="/people/assignments"><ProtectedPage><ResourceWorkspace config={{ eyebrow: "Work allocation", title: "Assignments that match the day’s reality.", description: "Find cleaner-site assignments and schedules, then use the backend-controlled lifecycle actions for active, suspended, and ended work.", endpoint: "/assignments", filterLabel: "assignments" }} /></ProtectedPage></Route>
    <Route path="/attendance"><ProtectedPage><AttendancePage /></ProtectedPage></Route>
    <Route path="/remuneration"><ProtectedPage><RemunerationPage /></ProtectedPage></Route>
    <Route path="/cleanliness"><ProtectedPage><CleanlinessPage /></ProtectedPage></Route>
    <Route path="/supervision/roster"><ProtectedPage><SupervisorRosterPage /></ProtectedPage></Route>
    <Route path="/supervision/timetable"><ProtectedPage><PersonalSupervisorSchedulerPage /></ProtectedPage></Route>
    <Route path="/inspections"><ProtectedPage><CleanlinessPage /></ProtectedPage></Route>
    <Route path="/operations/issues"><ProtectedPage><SiteIssuesPage /></ProtectedPage></Route>
    <Route path="/stores"><ProtectedPage><StockRequestsPage /></ProtectedPage></Route>
    <Route path="/reports"><ProtectedPage><ReportsPage /></ProtectedPage></Route>
    <Route path="/notifications"><ProtectedPage><NotificationsPage /></ProtectedPage></Route>
    <Route path="/inbox"><ProtectedPage><InboxPage /></ProtectedPage></Route>
    <Route path="/settings/profile"><ProtectedPage><ProfilePage /></ProtectedPage></Route>
    <Route component={NotFound} />
  </Switch></WouterRouter>;
}

export default function App() { return <ErrorBoundary><ThemeProvider defaultTheme="light"><TooltipProvider><AuthProvider><Router /><Toaster richColors position="top-right" /></AuthProvider></TooltipProvider></ThemeProvider></ErrorBoundary>; }
