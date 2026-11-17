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

// ---- scouts, competitions, matches ----------------------------------------------------
export const AGE_GROUPS = [
  "u15",
  "u16",
  "u17",
  "u18",
  "u19",
  "u21",
  "u23",
  "senior",
] as const;
export const COMPETITION_TYPES = [
  "league",
  "cup",
  "friendly",
  "youth_league",
  "international",
  "other",
] as const;
export const MATCH_STATUSES = [
  "scheduled",
  "live",
  "finished",
  "postponed",
  "cancelled",
] as const;
export const EVENT_TYPES = [
  "goal",
  "own_goal",
  "penalty",
  "yellow_card",
  "red_card",
  "substitution",
] as const;
export const STAT_FIELDS = [
  ["possession_pct", "Possession %"],
  ["shots", "Shots"],
  ["shots_on_target", "On target"],
  ["corners", "Corners"],
  ["fouls", "Fouls"],
  ["offsides", "Offsides"],
  ["yellow_cards", "Yellow cards"],
  ["red_cards", "Red cards"],
] as const;
// Mirrors the backend workflow so the UI only offers legal next steps.
export const MATCH_TRANSITIONS: Record<string, string[]> = {
  scheduled: ["live", "finished", "postponed", "cancelled"],
  live: ["finished", "cancelled"],
  finished: [],
  postponed: ["scheduled", "cancelled"],
  cancelled: ["scheduled"],
};

export type Scout = {
  id: string;
  user_id: string;
  full_name: string;
  email: string;
  org_role: string;
  bio: string | null;
  experience_years: number | null;
  positions: string[];
  age_groups: string[];
  regions: string[];
  is_active: boolean;
  can_edit: boolean;
  created_at: string;
};

export type Season = {
  id: string;
  competition_id: string;
  name: string;
  start_date: string;
  end_date: string;
  participant_count: number;
  match_count: number;
};
export type Competition = {
  id: string;
  name: string;
  country: string | null;
  competition_type: string;
  is_global: boolean;
  editable: boolean;
  season_count: number;
  created_at: string;
};
export type CompetitionDetail = Competition & { seasons: Season[] };
export type SeasonDetail = Season & {
  competition_name: string;
  editable: boolean;
  participants: { club_id: string; club_name: string; is_reference: boolean }[];
};

export type MatchSummary = {
  id: string;
  competition_id: string;
  competition_name: string;
  season_id: string;
  season_name: string;
  home_club_id: string;
  home_club_name: string;
  away_club_id: string;
  away_club_name: string;
  kickoff_at: string;
  venue: string | null;
  round_label: string | null;
  status: string;
  home_score: number | null;
  away_score: number | null;
  is_global: boolean;
  editable: boolean;
};
export type MatchEvent = {
  id: string;
  event_type: string;
  minute: number;
  club_id: string;
  club_name: string;
  player_id: string | null;
  player_name: string | null;
  description: string | null;
};
export type StatsSide = Partial<
  Record<(typeof STAT_FIELDS)[number][0], number | null>
>;
export type MatchDetail = MatchSummary & {
  events: MatchEvent[];
  statistics: { home: StatsSide | null; away: StatsSide | null };
};
