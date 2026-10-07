export interface UserProfile {
  id: number;
  user_id: number;
  name: string | null;
  phone: string | null;
  address: string | null;
}

export type UserRole = "admin" | "manager" | "user";

export interface AuthenticatedUser {
  id: number;
  email: string;
  is_active: boolean;
  role: UserRole;
  created_at: string;
  profile: UserProfile | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
}

export interface RegisteredUser {
  id: number;
  email: string;
  is_active: boolean;
  role: UserRole;
  created_at: string;
}

export type SessionStatus =
  | "loading"
  | "authenticated"
  | "unauthenticated"
  | "error";

export interface SessionSnapshot {
  status: SessionStatus;
  user: AuthenticatedUser | null;
  error: string | null;
}