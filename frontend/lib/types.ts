export type Organization = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  status: string;
  created_at: string;
};

export type Club = {
  id: string;
  organization_id: string | null;
  is_reference: boolean;
  name: string;
  short_name: string | null;
  country: string | null;
  city: string | null;
  description: string | null;
  founded_year: number | null;
  logo_url: string | null;
  website: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  created_at: string;
};

export type Page<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

export type Member = {
  id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  status: string;
  joined_at: string;
};

export type Invitation = {
  id: string;
  email: string;
  role: string;
  status: string;
  expires_at: string;
  created_at: string;
  accept_url: string | null;
};

export type Dashboard = {
  organization: Organization;
  clubs: number;
  members: number;
  pending_invitations: number;
};

export const ORG_ROLES = [
  "club_owner",
  "club_admin",
  "recruitment_manager",
  "scout",
  "coach",
] as const;

export const ROLE_LABELS: Record<string, string> = {
  club_owner: "Club Owner",
  club_admin: "Club Administrator",
  recruitment_manager: "Recruitment Manager",
  scout: "Scout",
  coach: "Coach",
};
