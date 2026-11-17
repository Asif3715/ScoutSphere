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

// ---- players & teams ------------------------------------------------------------------
export const POSITION_GROUPS: Record<string, string[]> = {
  goalkeeper: ["GK"],
  defender: ["CB", "LB", "RB", "LWB", "RWB"],
  midfielder: ["CDM", "CM", "CAM", "LM", "RM"],
  forward: ["LW", "RW", "CF", "ST"],
};
export const POSITIONS = Object.values(POSITION_GROUPS).flat();
export const FEET = ["left", "right", "both"] as const;
export const VISIBILITIES = ["private", "network", "public"] as const;
export const VISIBILITY_LABELS: Record<string, string> = {
  private: "Private (my organization only)",
  network: "Network (all ScoutSphere organizations)",
  public: "Public profile (adults only)",
};
export const SPELL_TYPES = ["permanent", "loan", "youth", "trial"] as const;
export const MEDIA_KINDS = ["video", "image", "document"] as const;
export const TEAM_TYPES = [
  "senior",
  "u23",
  "u21",
  "u19",
  "u18",
  "u17",
  "u16",
  "academy",
  "womens",
  "other",
] as const;

export type CurrentClub = { club_id: string; club_name: string };

export type PlayerSummary = {
  id: string;
  full_name: string;
  age: number;
  is_minor: boolean;
  nationality: string | null;
  primary_position: string | null;
  current_club: CurrentClub | null;
  is_owner: boolean;
};

export type Player = PlayerSummary & {
  date_of_birth: string;
  height_cm: number | null;
  weight_kg: number | null;
  preferred_foot: string | null;
  secondary_positions: string[];
  biography: string | null;
  profile_picture_url: string | null;
  visibility: string;
  created_at: string;
};

export type DuplicateCandidate = {
  id: string;
  full_name: string;
  date_of_birth: string;
  nationality: string | null;
  similarity: number;
};

export type Career = {
  id: string;
  club_id: string;
  club_name: string;
  team_label: string | null;
  spell_type: string;
  start_date: string;
  end_date: string | null;
  appearances: number | null;
  goals: number | null;
  assists: number | null;
  editable: boolean;
  managed_by_squad: boolean;
};

export type Media = {
  id: string;
  kind: string;
  title: string;
  url: string;
  created_at: string;
};

export type Team = {
  id: string;
  club_id: string;
  club_name: string;
  name: string;
  team_type: string;
  active_players: number;
  created_at: string;
};

export type SquadPlayer = {
  membership_id: string;
  player_id: string;
  full_name: string;
  age: number;
  is_minor: boolean;
  nationality: string | null;
  primary_position: string | null;
  position: string | null;
  position_group: string | null;
  squad_number: number | null;
  registered_on: string;
  left_on: string | null;
  status: string;
};

export type Squad = {
  team: Team;
  players: SquadPlayer[];
  counts_by_group: Record<string, number>;
};
