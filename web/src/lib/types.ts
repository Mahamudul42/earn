export interface Article {
  /** Topic label shown above the headline (e.g. "Iran war", "Technology"). */
  label: string;
  headline: string;
  summary: string;
  /** Thumbnail image URL (Associated Press preview). */
  image?: string;
  /** Source article link. */
  url?: string;
}

interface NewsletterSection {
  name: string;
  articles: Article[];
}

export interface Newsletter {
  slug: string;
  title: string;
  edition_label: string;
  sections: NewsletterSection[];
}

export interface ConditionConfig {
  condition: number;
  condition_label: string;
  prompt: string;
  base_explanation: string;
  instruction: string;
  guidance: string;
  example: string;
  intro: string;
  interactive: boolean;
}

export interface Session {
  public_id: string;
  condition: number;
  status: string;
  newsletter: Newsletter;
  condition_config: ConditionConfig;
  consent_text: string;
}

export interface AssistantTurn {
  action: "none" | "suggestion" | "question" | "ok";
  message: string;
  /** How many assistant rounds have run in this conversation (Condition 3). */
  assistant_turns?: number;
}

/** One bubble in the Condition-3 feedback-assistant conversation. */
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  action?: "suggestion" | "question" | "ok";
}

export interface SurveyAnswers {
  effort: number; // How much effort did it take to write your feedback?
  express: number; // How much were you able to express what you wanted?
  reflect: number; // How much does your feedback reflect what you actually want?
  understand: number; // Would someone reading your feedback understand what you want changed?
}

// --- Researcher ------------------------------------------------------------
interface Rating {
  id: number;
  rater_username: string;
  target_specificity: number;
  direction_operation: number;
  collection_allocation: number;
  context_persistence: number;
  system_feasibility: number;
  target_level: string;
  notes: string;
  total: number;
  created_at: string;
}

export interface FeedbackDetail {
  id: number;
  public_id: string;
  condition: number;
  newsletter: string;
  recruitment_source: string;
  study_phase: "main" | "pilot" | "preview";
  initial_text: string;
  final_text: string;
  assistant_action: string;
  assistant_message: string;
  chat_log: ChatMessage[];
  final_draft: string;
  revision_count: number;
  time_on_task_seconds: number | null;
  ratings: Rating[];
  mean_total: number | null;
  created_at: string;
}

export interface Overview {
  total_participants: number;
  completed: number;
  responses_with_final_text: number;
  responses_rated: number;
  per_condition: Record<
    string,
    { label: string; n: number; completed: number }
  >;
  cells: { condition: number; newsletter__slug: string; n: number }[];
}

export interface UserInfo {
  id: number;
  username: string;
  email: string;
  is_researcher: boolean;
  role: "manager" | "rater";
  can_manage_raters: boolean;
  is_active: boolean;
  rating_count: number;
  last_login: string | null;
  date_joined: string;
}

export interface BlindFeedback {
  id: number;
  final_text: string;
}
