// Single source of truth for "what can this role do." Before this file, the same
// role → allow-list pairs were copy-pasted independently across App.tsx, Sidebar.tsx,
// UsageCard.tsx, DashboardPage.tsx, AuditPage.tsx, TlActionsPage.tsx and SettingsPage.tsx.
// Add new gates here instead of inlining another `role === 'X'` check at a call site.

export type Role = 'Owner' | 'Admin' | 'Auditor'

export const ALL_ROLES: Role[] = ['Auditor', 'Admin', 'Owner']

export type Feature =
  // Sidebar / top-level tab gating (App.tsx TAB_ROLES, Sidebar.tsx ALL_ITEMS)
  | 'users-tab'
  | 'scoring-tab'
  | 'tl-actions-tab'
  | 'phrase-management-tab'
  | 'settings-tab'
  // UsageCard quota title
  | 'admin-quota-view'
  // Dashboard/Audit pages: Auditor is restricted to Agent Audit only
  | 'campaign-audit'
  // TL Actions page
  | 'tl-owner-actions'
  | 'podio-connection'
  // Settings page sub-sections
  | 'quota-control'
  | 'admin-quota-dashboard'
  | 'system-health'
  | 'app-config'
  | 'admin-manage-users'
  | 'user-edit'
  | 'user-sessions'
  | 'dashboard-sharing'
  | 'create-admin-user'

const FEATURE_ROLES: Record<Feature, readonly Role[]> = {
  'users-tab': ['Owner', 'Admin'],
  'scoring-tab': ['Owner', 'Admin'],
  'tl-actions-tab': ['Owner', 'Admin'],
  'phrase-management-tab': ['Owner'],
  'settings-tab': ['Owner', 'Admin'],

  'admin-quota-view': ['Owner', 'Admin'],

  'campaign-audit': ['Owner', 'Admin'],

  'tl-owner-actions': ['Owner'],
  'podio-connection': ['Owner', 'Admin'],

  'quota-control': ['Owner'],
  'admin-quota-dashboard': ['Admin'],
  'system-health': ['Owner'],
  'app-config': ['Owner'],
  'admin-manage-users': ['Admin'],
  'user-edit': ['Owner'],
  'user-sessions': ['Owner'],
  'dashboard-sharing': ['Owner'],
  'create-admin-user': ['Owner'],
}

// Fails closed: an unknown/not-yet-loaded role never gets a restricted feature.
export function canAccess(role: string | null | undefined, feature: Feature): boolean {
  return !!role && FEATURE_ROLES[feature].includes(role as Role)
}

// Who can delete whom in Settings > Manage Users: Owner accounts are never deletable;
// Owners can delete anyone else; Admins can only delete Auditors.
export function canDeleteUser(actingRole: string | null | undefined, targetRole: string): boolean {
  if (targetRole === 'Owner') return false
  if (actingRole === 'Owner') return true
  return actingRole === 'Admin' && targetRole === 'Auditor'
}
