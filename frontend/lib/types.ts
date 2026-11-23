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
  /** Signed path (or external link) to a 160px square; null when none or withheld. */
  photo_thumb_url: string | null;
};

export type Player = PlayerSummary & {
  date_of_birth: string;
  height_cm: number | null;
  weight_kg: number | null;
  preferred_foot: string | null;
  secondary_positions: string[];
  biography: string | null;
  profile_picture_url: string | null;
  photo_url: string | null;
  has_uploaded_photo: boolean;
  visibility: string;
  created_at: string;
  /** The player has their own account, which now controls the profile's visibility. */
  claimed?: boolean;
  open_to_offers?: boolean;
  contact_email?: string | null;
};

// ---- player accounts ------------------------------------------------------------------
export type CareerSpell = {
  club_name: string;
  team_label: string | null;
  spell_type: string;
  start_date: string;
  end_date: string | null;
  appearances: number | null;
  goals: number | null;
  assists: number | null;
};

export type SelfProfile = {
  player_id: string;
  full_name: string;
  date_of_birth: string;
  age: number;
  is_minor: boolean;
  nationality: string | null;
  height_cm: number | null;
  weight_kg: number | null;
  preferred_foot: string | null;
  primary_position: string | null;
  secondary_positions: string[];
  biography: string | null;
  photo_url: string | null;
  photo_thumb_url: string | null;
  has_uploaded_photo: boolean;
  visibility: string;
  open_to_offers: boolean;
  contact_email: string | null;
  current_club: { club_id: string; club_name: string } | null;
  managed_by: string | null;
  career: CareerSpell[];
};

export type Claimable = {
  player_id: string;
  full_name: string;
  age: number;
  nationality: string | null;
  primary_position: string | null;
  current_club: { club_id: string; club_name: string } | null;
  reviewed_by: string;
};

export type MyClaim = {
  id: string;
  status: "pending" | "approved" | "rejected" | "cancelled";
  player_id: string;
  player_name: string;
  reviewed_by: string;
  message: string | null;
  decision_note: string | null;
  created_at: string;
  decided_at: string | null;
};

export type OrgClaim = {
  id: string;
  status: "pending" | "approved" | "rejected" | "cancelled";
  created_at: string;
  message: string | null;
  requester_name: string;
  requester_email: string;
  player_id: string;
  player_name: string;
  player_age: number;
  player_position: string | null;
  decision_note: string | null;
  decided_at: string | null;
  decided_by_name: string | null;
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

// ---- assignments, reports, notifications ---------------------------------------------
export const RATING_GROUPS: Record<string, string[]> = {
  technical: [
    "passing",
    "ball_control",
    "dribbling",
    "shooting",
    "first_touch",
    "crossing",
  ],
  physical: ["speed", "acceleration", "strength", "stamina", "agility"],
  tactical: [
    "positioning",
    "decision_making",
    "awareness",
    "defensive_contribution",
    "movement",
  ],
  mental: ["work_rate", "discipline", "confidence", "leadership"],
};
export const RECOMMENDATIONS = [
  "strongly_recommend",
  "recommend",
  "monitor",
  "not_recommended",
] as const;
export const ASSIGNMENT_STATUSES = [
  "draft",
  "assigned",
  "accepted",
  "in_progress",
  "submitted",
  "under_review",
  "approved",
  "rejected",
  "cancelled",
] as const;
export const REPORT_STATUSES = [
  "draft",
  "submitted",
  "revision_requested",
  "approved",
  "rejected",
] as const;

export const label = (v: string) => v.replace(/_/g, " ");

export type AssignmentSummary = {
  id: string;
  title: string;
  status: string;
  target_type: string;
  target_id: string;
  target_label: string;
  scout_id: string;
  scout_name: string;
  deadline: string | null;
  is_overdue: boolean;
  instructions: string | null;
  criteria: string | null;
  report_count: number;
  created_at: string;
};
export type AssignmentDetail = AssignmentSummary & {
  history: {
    from_status: string | null;
    to_status: string;
    actor_name: string | null;
    note: string | null;
    created_at: string;
  }[];
  reports: {
    id: string;
    player_name: string;
    status: string;
    recommendation: string | null;
  }[];
  allowed_transitions: string[];
  is_mine: boolean;
};
export type AssignmentStats = {
  counts: Record<string, number>;
  overdue: number;
  due_soon: number;
};

export type ReportSummary = {
  id: string;
  status: string;
  player_id: string;
  player_name: string;
  scout_id: string;
  scout_name: string;
  match_label: string | null;
  observed_on: string;
  recommendation: string | null;
  assignment_id: string | null;
  assignment_title: string | null;
  current_version: number;
  submitted_at: string | null;
};
export type ReportDetail = ReportSummary & {
  match_id: string | null;
  club_id: string | null;
  club_name: string | null;
  position_observed: string | null;
  strengths: string | null;
  weaknesses: string | null;
  development_areas: string | null;
  general_observations: string | null;
  ratings: Record<string, number>;
  versions: { version: number; created_at: string }[];
  reviews: {
    version: number;
    decision: string;
    comment: string | null;
    reviewer_name: string | null;
    created_at: string;
  }[];
  is_mine: boolean;
  can_edit: boolean;
  can_review: boolean;
  created_at: string;
};

export type AppNotification = {
  id: string;
  type: string;
  title: string;
  body: string | null;
  link_path: string | null;
  organization_id: string | null;
  read: boolean;
  created_at: string;
};

// ---- recruitment -----------------------------------------------------------------------
export const PRIORITIES = ["low", "medium", "high", "urgent"] as const;
export const REQUIREMENT_STATUSES = [
  "draft",
  "open",
  "on_hold",
  "fulfilled",
  "cancelled",
] as const;
export const STAGE_ORDER = [
  "discovered",
  "under_evaluation",
  "shortlisted",
  "scout_assigned",
  "report_submitted",
  "under_review",
  "trial_proposed",
  "negotiation",
  "signed",
] as const;
export const STAGES = [...STAGE_ORDER, "rejected", "archived"] as const;

export type RequirementSummary = {
  id: string;
  title: string;
  position: string;
  priority: string;
  status: string;
  candidate_count: number;
  created_at: string;
};
export type Requirement = RequirementSummary & {
  min_age: number | null;
  max_age: number | null;
  nationality: string | null;
  preferred_foot: string | null;
  min_appearances: number | null;
  budget_min: number | null;
  budget_max: number | null;
  currency: string | null;
  contract_notes: string | null;
  instructions: string | null;
  attributes: Record<string, number>;
  pipeline_counts: Record<string, number>;
  created_by_name: string | null;
  allowed_statuses: string[];
};
export type Criterion = {
  name: string;
  required: string;
  actual: string | null;
  met: boolean;
};
export type CandidateMatch = {
  player: PlayerSummary;
  criteria: Criterion[];
  report_count: number;
  in_pipeline: boolean;
};
export type Candidate = {
  id: string;
  requirement_id: string;
  requirement_title: string;
  player_id: string;
  player_name: string;
  age: number;
  primary_position: string | null;
  stage: string;
  notes: string | null;
  assignment_id: string | null;
  assignment_status: string | null;
  created_at: string;
  updated_at: string;
  photo_thumb_url: string | null;
  /** The team of this organization the player is registered with, if any. */
  squad_team_id?: string | null;
  squad_team_name?: string | null;
};
export type CandidateDetail = Candidate & {
  history: {
    from_stage: string | null;
    to_stage: string;
    actor_name: string | null;
    note: string | null;
    created_at: string;
  }[];
  allowed_stages: string[];
};
export type ShortlistSummary = {
  id: string;
  name: string;
  description: string | null;
  priority: string;
  requirement_id: string | null;
  requirement_title: string | null;
  player_count: number;
  is_owner: boolean;
  owner_name: string | null;
  created_at: string;
};
export type ShortlistDetail = ShortlistSummary & {
  players: {
    player: PlayerSummary;
    notes: string | null;
    priority: string;
    added_at: string;
    pipeline: {
      requirement_id: string;
      requirement_title: string;
      stage: string;
    }[];
  }[];
  shared_with: { user_id: string; full_name: string }[];
};
export type ComparePlayer = {
  player: PlayerSummary;
  date_of_birth: string;
  secondary_positions: string[];
  height_cm: number | null;
  weight_kg: number | null;
  preferred_foot: string | null;
  objective: {
    appearances: number | null;
    goals: number | null;
    assists: number | null;
    recent_club: string | null;
    recent_appearances: number | null;
    recent_goals: number | null;
    recent_assists: number | null;
    contract_status: string | null;
  };
  scouting: {
    approved_reports: number;
    ratings: Record<string, number>;
    recommendations: Record<string, number>;
    latest_recommendation: string | null;
  };
  suitability: Criterion[] | null;
};
export type CompareResult = {
  players: ComparePlayer[];
  attributes: string[];
  leaders: Record<string, string[]>;
  requirement_title: string | null;
};
