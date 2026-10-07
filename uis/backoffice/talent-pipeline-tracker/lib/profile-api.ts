import type { NexovaApiClient } from "./nexova-api";
import type { UserProfile } from "@/types/auth";

export interface ProfileUpdatePayload {
  name: string;
  phone: string;
  address: string;
}

type ProfileApiClient = Pick<NexovaApiClient, "request">;

export async function getMyProfile(
  client: ProfileApiClient,
): Promise<UserProfile | null> {
  try {
    return await client.request<UserProfile>("/profiles/me", { auth: true });
  } catch (error) {
    if (error instanceof Error && "status" in error && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export function updateMyProfile(
  client: ProfileApiClient,
  payload: ProfileUpdatePayload,
): Promise<UserProfile> {
  return client.request<UserProfile>("/profiles/me", {
    method: "PUT",
    auth: true,
    json: payload,
  });
}